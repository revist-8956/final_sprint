# Argo CD App of Apps

`root-application.yaml`이 `apps/`의 Application을 관리하고, 각 Application이 공식 Helm 차트로 KEDA와 Karpenter를 설치합니다. Argo CD가 `argocd` 네임스페이스에 이미 설치되어 있고 기본 프로젝트가 대상 저장소와 클러스터 리소스를 허용한다고 가정합니다.

## 배포 전 설정

1. 부모 Application의 `repoURL`, `targetRevision`이 실제 Argo CD에서 접근 가능한 저장소와 브랜치인지 확인하고 변경 사항을 해당 브랜치에 커밋합니다. private 저장소라면 Argo CD에 접근 자격 증명을 등록합니다.
2. KEDA 2.21.1은 Kubernetes 1.34~1.36에서 테스트되었습니다. 현재 `daily-eks.yaml`의 기본 버전은 1.37이므로, 실제 클러스터 버전에 맞는 지원 조합을 확인하고 변경한 뒤 배포합니다. Karpenter도 클러스터 버전과 차트의 호환성을 확인합니다.
3. `apps/karpenter.yaml`의 `settings.clusterName`을 실제 EKS 클러스터 이름으로 변경합니다. 기본값은 CloudFormation의 기본 클러스터 이름입니다.
4. `infra/cloudformation/daily-eks.yaml`의 변경 사항을 먼저 배포해 Karpenter 컨트롤러 IAM 역할·Pod Identity association, 노드 역할·instance profile 및 EKS Access Entry를 생성합니다. IAM 이름 지정 리소스가 있으므로 배포 명령에 `--capabilities CAPABILITY_NAMED_IAM`이 필요합니다. 기존 스택 업데이트 시 기존 파라미터를 유지하고 변경 집합을 검토합니다.
5. `karpenter/nodeclass.yaml`의 instance profile, private subnet과 보안 그룹 태그, AMI alias를 실제 환경에 맞춥니다. 기본값은 `final-sprint-cluster` 및 `final-sprint` 프로젝트에 맞춰져 있습니다. AL2023 AMI `v20261112`는 서울 리전 EKS 1.37의 권장 릴리스 조회값이며, 배포 전 검증한 AMI로 교체하고 주기적으로 갱신합니다.
6. `karpenter/nodepool.yaml`은 `workload: app` 라벨, on-demand `t3.large`/`t3.xlarge`, CPU 8 한도로 구성합니다. 한도는 급격한 확장 중 일시적으로 초과될 수 있고 비용 상한은 아닙니다. 추가 노드는 두 private subnet에 생성될 수 있습니다. Spot 중단 처리 설정은 포함하지 않습니다.

Karpenter 컨트롤러는 기존 관리형 노드에서 실행되며 이 환경의 taint 없는 관리형 노드가 한 대이므로 replica를 1개로 설정했습니다. `karpenter` Application은 다중 소스로 Helm 차트와 Git의 NodePool·EC2NodeClass를 함께 동기화합니다. 최초 동기화가 CRD 준비 시점 때문에 실패하면 상태를 확인한 뒤 다시 동기화합니다. NodePool은 스케줄되지 않는 호환 Pod가 있을 때 노드를 생성하며, 기존 앱 Deployment의 리소스 요청과 `workload: app` 조건을 확인해야 합니다.

설정 및 커밋 후 최초 한 번 적용합니다.

```bash
kubectl apply -f k8s/argocd/root-application.yaml
kubectl get applications -n argocd
kubectl get pods -n keda
kubectl get pods -n karpenter
kubectl -n kube-system rollout status deployment/aws-load-balancer-controller
kubectl get ec2nodeclasses,nodepools
```

부모의 자동 prune은 `apps/`에서 제거한 자식 Application을 삭제합니다. 자식 Application에는 리소스 삭제용 finalizer가 없으므로 자식 Application 삭제만으로 설치된 리소스가 연쇄 삭제되지는 않습니다. 차트 리소스 변경은 자식 Application의 자동 sync와 prune으로 반영됩니다. 기존 워크로드와 CRD가 있다면 적용 전에 소유권과 업그레이드 경로를 확인합니다.

참고: [KEDA Kubernetes 호환성](https://keda.sh/docs/2.21/operate/cluster/), [Karpenter 시작 안내 및 AWS 준비](https://karpenter.sh/docs/getting-started/getting-started-with-karpenter/), [Karpenter 호환성](https://karpenter.sh/v1.15/upgrading/compatibility/).

## Load Balancer Controller 복원

Load Balancer Controller는 이 App of Apps의 관리 대상이 아닙니다. AWS Backup에 포함된 기존 Helm 설치와 서비스 계정을 복원합니다. Daily 스택은 별도의 컨트롤러 IAM 역할과 Pod Identity association을 준비하지만, 기존 IRSA 주석을 제거하고 Pod를 교체하기 전까지 자동으로 전환되지 않습니다. 기존 클러스터를 내리기 전에 Pod Identity로 전환해 백업하고, 전환 전 백업의 경우 복원 시 IRSA 주석을 제거합니다. 인증 전환과 복원 검증 방법은 [CloudFormation 안내](../../infra/cloudformation/README.md#aws-load-balancer-controller-aws-권한과-기존-irsa-전환)를 참고합니다.

기존 EKS 백업에서 재생성할 때는 daily 스택으로 인프라와 IAM을 만든 뒤 AWS Backup으로 Argo CD와 Application을 포함한 Kubernetes 리소스를 복원합니다. 백업에 포함된 리소스가 정상 복원되었다면 Argo CD 재설치나 부모 Application 재등록은 필요하지 않습니다.
