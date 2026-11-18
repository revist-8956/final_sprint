# EKS 학습 환경: 유지할 스택과 일일 스택

이 디렉터리의 두 템플릿은 **AWS 인프라만 생성**합니다. 실제 AWS 배포·백업·복원은 실행하지 않았습니다.

| 파일 | 역할 | 일일 종료 시 |
|---|---|---|
| [`bootstrap.yaml`](bootstrap.yaml) | VPC, 두 AZ의 public/private subnet 각 2개, IGW, route table, IAM 역할, Backup vault | 유지 |
| [`daily-eks.yaml`](daily-eks.yaml) | NAT Gateway·EIP·private 기본 경로, EKS, 워커 2개, 접근 권한, 기본 Add-on·EBS CSI | 데이터 정리 후 삭제 |

현재 기준은 **관측 워커 `t3.xlarge` 1대 + 앱 워커 `t3.large` 1대**입니다. 이전 [`eks-cloudformation-backup-plan.md`](../../docs/eks-cloudformation-backup-plan.md)의 동일한 `m6i.large` 2대 견적은 과거 가정이며 현재 구성의 견적이 아닙니다.

## 생성 범위와 남은 작업

- EKS 제어 영역에는 두 AZ의 **private subnet**을 제공하지만, 두 워커는 EBS 연결을 단순화하려고 **private subnet A의 같은 AZ**에 배치합니다. 고가용성 구성이 아닙니다.
- 두 워커의 루트 EBS는 기본 20 GiB, 암호화된 gp3이며 `DeleteOnTermination: true`입니다.
- **앱 데이터 EBS는 생성하지 않습니다. 관측 데이터 EBS도 이 템플릿에서 미리 만들지 않습니다.** 이후 EBS CSI 기반 PVC로 별도 생성합니다.
- public subnet A에 **NAT Gateway 1개와 EIP**를 만들고 두 private subnet의 기본 경로를 연결합니다. 워커에는 public IPv4를 주지 않으며 외부 통신은 NAT를 통과합니다. Bastion·LoadBalancer·SSH 인바운드는 만들지 않습니다.
- **NAT Gateway·EIP·private 기본 경로는 daily 스택 소유**입니다. daily 스택을 삭제하면 함께 정리하여 쉬는 날 NAT 시간 요금이 계속 발생하지 않도록 합니다. 실제 삭제·EIP 해제 완료를 확인합니다.
- NAT 1개는 HA 구성이 아닙니다. 향후 subnet B에 워커를 배치하면 NAT가 있는 AZ A까지의 교차 AZ 트래픽 비용도 고려해야 합니다.
- Prometheus/Loki/Tempo/Grafana/Alloy, ArgoCD, KEDA, Karpenter, AWS Load Balancer Controller와 앱의 Kubernetes 배포는 별도입니다. 컨트롤러의 AWS 권한은 daily 스택에 포함합니다.
- **EKS 백업 opt-in, StorageClass/PVC, 백업·복원·정리 자동화는 포함하지 않습니다.** 스택을 다시 생성해도 데이터는 자동 복원되지 않습니다.

Git은 파일 보관소입니다. CloudFormation이 GitHub raw URL을 자동으로 읽는 것으로 가정하지 마세요. 저장소를 clone한 뒤 로컬 `--template-file`을 사용하거나, 콘솔에서 파일 업로드 또는 지원되는 S3 TemplateURL을 사용합니다.

### 네트워크 흐름

```text
private A: 관측 워커 + 앱 워커 ─┐
private B: EKS 연결·향후 배치용 ─┴→ public A: NAT Gateway + EIP → IGW → Internet

AWS 관리 EKS 컨트롤 플레인 ↔ private A/B의 EKS 연결 ENI
public B: 별도 AZ의 public subnet 유지, NAT는 배치하지 않음
```

첫 줄의 화살표는 **워커의 외부 접속 방향**입니다. NAT가 외부에서 private 워커로의 새 인바운드 연결을 열어 주지는 않습니다. 컨트롤 플레인은 AWS 관리 영역에 있으며, private subnet B에 직접 만든 관리 노드가 있는 것은 아닙니다.

## 1. 배포 전 준비

AWS CLI v2, kubectl, Python 3와 배포 권한이 필요합니다. CLI 배포·조회에는 먼저 배포 권한이 있는 AWS 자격증명으로 로그인해야 합니다. 로컬 프로필/SSO를 사용하고 **액세스 키·토큰을 Git에 넣지 않습니다.** 아래 명령은 저장소 루트에서 실행합니다. Git sync를 사용한다면 스택 파라미터는 콘솔이나 배포 파일에 지정할 수 있습니다.

```bash
set -euo pipefail
export AWS_REGION=ap-northeast-2
export BOOTSTRAP_STACK=final-sprint-bootstrap
export DAILY_STACK=final-sprint-daily
export CLUSTER_NAME=final-sprint-cluster
```

- 세 `CLUSTER_ADMIN_USER...ARN`은 서로 다른 기존 IAM 사용자의 `arn:aws:iam::계정:user/사용자` 형식 ARN입니다. 역할 ARN이나 STS 세션 ARN은 사용할 수 없습니다. 각 사용자에게 EKS 클러스터 전체 관리자 권한을 부여하므로 사용자마다 본인의 자격증명을 사용하고 공유하지 않습니다.
- 요청에 따라 배포 대상 계정의 **AWS root 사용자도 별도 Access Entry의 클러스터 전체 관리자**로 등록합니다. root ARN은 `AWS::AccountId`로 자동 구성하며 사용자가 입력하지 않습니다. root 사용은 강력한 권한이므로 비상용으로 한정하고 MFA 등으로 보호하세요. [AWS 권고](https://docs.aws.amazon.com/eks/latest/userguide/security-iam.html)
- 최초 등록은 root가 배포 설정을 준비·승인하는 운영 절차로 정합니다. Git sync로 배포하면 실제 AWS 리소스 생성은 구성된 서비스 역할 등을 통해 수행될 수 있으며, 이 템플릿은 실행 주체가 root인지 강제하지 않습니다.
- `ADMIN_PUBLIC_CIDR`은 `/24`~`/32`만 허용하며 일반적으로 공통 VPN 출구의 `/32`를 사용합니다. 하나의 CIDR만 받으므로 서로 다른 네트워크라면 공통 VPN 등 접속 경로를 먼저 정합니다. `0.0.0.0/0`는 허용하지 않습니다.
- public EKS API는 위 CIDR로 제한하고 private API를 활성화합니다. 워커는 VPC 내부 endpoint로 접속합니다. SSH 대신 각자의 kubectl을 사용하며, 대시보드는 설치 후 `kubectl port-forward` 등으로 접근합니다.
- 아직 STANDARD 지원 중인 `EKS_VERSION`을 선택하고 복원 시 동일하게 유지합니다. `SupportType: STANDARD`는 확장 지원 과금을 피하지만 **표준 지원 종료 시 자동 업그레이드 대상**이므로 영구 버전 고정을 의미하지 않습니다.

확인용 읽기 명령:

```bash
aws eks describe-cluster-versions --region "$AWS_REGION"
aws ec2 describe-availability-zones --region "$AWS_REGION" \
  --filters Name=zone-type,Values=availability-zone Name=state,Values=available \
  --query 'AvailabilityZones[].ZoneName' --output table
aws sts get-caller-identity
```

## 2. Bootstrap: 최초 한 번 생성하고 유지

같은 계정·리전에 사용할 bootstrap 스택이 이미 생성되어 있다면 다시 만들지 않고 outputs를 확인한 뒤 백업 opt-in 단계로 진행합니다. 아래는 CLI로 처음 생성하는 경우입니다.

```bash
# 먼저 사용 가능한 서로 다른 AZ 이름을 환경 변수로 설정합니다.
: "${AVAILABILITY_ZONE_A:?서울 리전에서 사용할 첫 번째 AZ 이름을 설정하세요}"
: "${AVAILABILITY_ZONE_B:?첫 번째와 다른 두 번째 AZ 이름을 설정하세요}"

aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name "$BOOTSTRAP_STACK" \
  --template-file infra/cloudformation/bootstrap.yaml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    AvailabilityZoneA="$AVAILABILITY_ZONE_A" \
    AvailabilityZoneB="$AVAILABILITY_ZONE_B"

aws cloudformation update-termination-protection \
  --region "$AWS_REGION" \
  --stack-name "$BOOTSTRAP_STACK" \
  --enable-termination-protection

aws cloudformation describe-stacks \
  --region "$AWS_REGION" --stack-name "$BOOTSTRAP_STACK" \
  --query 'Stacks[0].Outputs' --output table
```

`AvailabilityZoneA/B`는 위 조회 결과에서 사용 가능한 서로 다른 AZ 이름을 선택합니다. 두 워커는 A에 생성합니다.

Bootstrap과 daily 스택은 **같은 계정·리전**에서 사용합니다. daily 스택은 bootstrap의 export를 참조하므로 사용하는 동안 기반 네트워크·IAM 역할을 교체하지 않습니다.

**Bootstrap 하나당 daily 스택 하나만 동시에 사용합니다.** 두 private route table의 기본 경로를 daily 스택이 관리하므로 같은 bootstrap에 daily 스택을 중복 생성하면 경로 소유권이 충돌합니다.

- 기본 Backup vault 암호화는 AWS 관리형 Backup 키를 사용합니다. 별도의 고객 관리형 키는 생성하지 않습니다.
- 기존 CMK가 필요하면 `BackupVaultKmsKeyArn`에 같은 리전의 키 ARN을 전달합니다. 키 정책 허용도 필요합니다. **Vault 키와 원본 EBS 암호화 키는 다를 수 있으며 둘 다 복원 기간 동안 유지해야 합니다.**
- Vault에는 `DeletionPolicy: Retain`과 `UpdateReplacePolicy: Retain`이 있습니다. bootstrap을 삭제해도 남을 수 있고 보관 비용도 계속 발생합니다. 이 설정은 KMS 키 삭제까지 막아 주는 장치가 아닙니다.
- IAM은 학습용 AWS 관리형 정책을 사용합니다. 초기 네트워킹을 위해 두 워커의 공통 node role에 CNI 권한을 둡니다. 운영 환경용 최소 권한 설계나 신뢰할 수 없는 다중 테넌트 격리는 아닙니다.

### AWS Backup EKS opt-in: 계정·리전별 최초 설정

CloudFormation에 EKS opt-in 리소스가 없으므로 별도로 설정합니다. 콘솔의 **AWS Backup → Settings → Configure resources → EKS**에서도 할 수 있습니다.

CLI를 사용한다면 기존 설정을 읽어 보존한 뒤 EKS를 추가합니다. 다음은 **계정의 리전 설정을 변경하는 명령**입니다.

```bash
aws backup describe-region-settings --region "$AWS_REGION"

OPT_IN_FILE="$(mktemp)"
aws backup describe-region-settings --region "$AWS_REGION" \
  --query ResourceTypeOptInPreference --output json \
  | python3 -c 'import json,sys; p=json.load(sys.stdin); p["EKS"]=True; json.dump(p,sys.stdout)' \
  > "$OPT_IN_FILE"

aws backup update-region-settings --region "$AWS_REGION" \
  --resource-type-opt-in-preference "file://$OPT_IN_FILE"
rm -f "$OPT_IN_FILE"
```

## 3. Daily EKS: 최초 생성과 다음 날 재생성에 같은 파일 사용

### 3-1. Git sync로 배포하는 경우

Git sync 배포 파일을 직접 제공하는 경우 `parameters`에 `ClusterAdminUserArn`, `ClusterAdminUser2Arn`, `ClusterAdminUser3Arn`, `AdminPublicAccessCidr`를 지정합니다. 이전 이름인 `ClusterAdminRoleArn`은 더 이상 사용하지 않습니다. 사용자 ARN은 실제 계정 값으로 교체하고, 액세스 키는 배포 파일에 넣지 않습니다. Git sync는 커밋을 실제 스택에 반영할 수 있으므로 변경사항을 배포 전에 확인합니다.

예를 들어 `infra/cloudformation/daily-eks-deployment.yaml`의 형식은 다음과 같습니다. `123456789012`, 사용자 이름, IP는 **실제 값이 아닌 예시**이며 모두 교체해야 합니다. 사용자 ARN 3개는 서로 달라야 합니다. root ARN은 입력하지 않습니다.

```yaml
template-file-path: infra/cloudformation/daily-eks.yaml
parameters:
  ClusterAdminUserArn: "arn:aws:iam::123456789012:user/user1"
  ClusterAdminUser2Arn: "arn:aws:iam::123456789012:user/user2"
  ClusterAdminUser3Arn: "arn:aws:iam::123456789012:user/user3"
  AdminPublicAccessCidr: "203.0.113.10/32"
tags: {}
```

이 파일을 수정한다고 클러스터가 즉시 등록되는 것은 아닙니다. Git sync가 감시하는 브랜치에 반영된 뒤 스택 생성·업데이트가 성공해야 합니다. **Git sync는 반영 즉시 실제 AWS 자원에 영향을 줄 수 있으므로** 커밋·병합 전에 파라미터와 변경 사항을 검토합니다. Access Entry가 기존에 존재한다면 중복 생성이나 교체 충돌이 없는지도 확인합니다.

### 3-2. CLI로 배포하는 경우 — Git sync의 대안

```bash
# 먼저 다음 값들을 환경 변수로 설정합니다.
: "${EKS_VERSION:?현재 EKS STANDARD 지원 중인 Kubernetes 버전을 설정하세요}"
: "${CLUSTER_ADMIN_USER_ARN:?첫 번째 IAM 사용자 ARN을 설정하세요}"
: "${CLUSTER_ADMIN_USER_2_ARN:?두 번째 IAM 사용자 ARN을 설정하세요}"
: "${CLUSTER_ADMIN_USER_3_ARN:?세 번째 IAM 사용자 ARN을 설정하세요}"
: "${ADMIN_PUBLIC_CIDR:?관리자 또는 공통 VPN의 공인 IPv4 CIDR을 설정하세요}"

aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name "$DAILY_STACK" \
  --template-file infra/cloudformation/daily-eks.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    BootstrapStackName="$BOOTSTRAP_STACK" \
    ClusterName="$CLUSTER_NAME" \
    KubernetesVersion="$EKS_VERSION" \
    ClusterAdminUserArn="$CLUSTER_ADMIN_USER_ARN" \
    ClusterAdminUser2Arn="$CLUSTER_ADMIN_USER_2_ARN" \
    ClusterAdminUser3Arn="$CLUSTER_ADMIN_USER_3_ARN" \
    AdminPublicAccessCidr="$ADMIN_PUBLIC_CIDR"
```

### 3-3. kubectl 접속 확인

kubectl을 실행할 때는 먼저 세 IAM 사용자 ARN 중 본인에 해당하는 자격증명을 로컬 AWS 프로필에서 사용합니다. 다음은 **액세스 키 없이 IAM 콘솔 계정으로 로그인하는 예시**입니다. AWS CLI 2.32.0 이상과 해당 사용자의 `SignInLocalDevelopmentAccess` 권한이 필요합니다. 사용자마다 `eks:DescribeCluster` 권한과 허용된 네트워크 경로도 필요합니다. [AWS CLI 로그인](https://docs.aws.amazon.com/signin/latest/userguide/command-line-sign-in.html)

```bash
aws login --profile final-sprint --region "$AWS_REGION"
export AWS_PROFILE=final-sprint
aws sts get-caller-identity
aws eks update-kubeconfig --region "$AWS_REGION" --name "$CLUSTER_NAME"

kubectl get nodes -L workload,topology.kubernetes.io/zone
kubectl get pods -n kube-system -o wide
```

### 기본값과 선택 파라미터

| 파라미터 | 기본값/동작 |
|---|---|
| `ObservabilityInstanceType` | `t3.xlarge` |
| `AppInstanceType` | `t3.large` |
| `ObservabilityRootVolumeGiB`, `AppRootVolumeGiB` | 각각 `20`; 데이터 PVC 용량과 별개 |
| `T3CpuCredits` | `standard`; 크레딧 소진 시 성능 제한. `unlimited`는 추가 CPU 요금 가능 |
| `NodeAmiReleaseVersion` | 생략 시 EKS 호환 기본 AL2023 release |
| `VpcCniAddonVersion`, `KubeProxyAddonVersion`, `CoreDnsAddonVersion`, `PodIdentityAgentAddonVersion`, `EbsCsiAddonVersion` | 생략 시 EKS 호환 기본값; 재현성이 필요하면 검증한 버전을 기록·고정 |

Add-on은 VPC CNI, kube-proxy, CoreDNS, Pod Identity Agent, EBS CSI입니다. EBS CSI의 Pod Identity association은 Add-on이 소유하므로 같은 service account에 중복 association을 만들지 않습니다.

### AWS Load Balancer Controller AWS 권한과 기존 IRSA 전환

Daily 스택은 `kube-system/aws-load-balancer-controller`용 IAM 역할과 EKS Pod Identity association을 생성합니다. 정책은 현재 설치된 AWS Load Balancer Controller **v2.14.0**의 공식 IAM 정책을 기준으로 고정합니다. 기존 Helm 설치와 Kubernetes 서비스 계정은 이 App of Apps가 관리하지 않으며 AWS Backup에서 복원합니다. 컨트롤러를 업그레이드할 때 해당 버전의 공식 IAM 정책도 함께 검토해야 합니다. public/private 서브넷의 ELB 검색 태그는 bootstrap 스택에 이미 있습니다.

2026-11-18 조회 시 기존 컨트롤러는 Helm으로 설치되어 있고, 별도의 `eksctl-final-sprint-cluster-addon-iamserviceaccount-kube-system-aws-load-balancer-controller` 스택이 만든 IRSA 역할을 사용하고 있습니다. 기존 역할과 정책은 새 daily 스택에 자동으로 가져오거나 삭제하지 않습니다. 기존 설정을 유지한 채 daily 스택의 변경 집합을 검토하고 배포한 다음, Pod Identity association과 Pod Identity Agent가 준비됐는지 확인합니다. 기존 Helm release 및 서비스 계정의 관리 방식을 유지합니다. 새 Pod Identity association은 전환 전까지 기존 IRSA 인증을 대체하지 않습니다.

IRSA 자격 증명은 Pod Identity보다 우선하므로 association 생성만으로 전환되지 않습니다. **현재 클러스터를 백업하고 종료하기 전에** 다음 절차로 Pod Identity로 전환하고 실제 AWS 접근을 검증합니다. 기존 역할 ARN을 기록한 뒤 서비스 계정 주석을 제거하고 컨트롤러 Pod를 교체합니다. Helm values 또는 다른 관리 도구에 해당 주석이 설정되어 있다면 재적용으로 되살아나지 않도록 해당 설정도 제거해야 합니다.

```bash
kubectl -n kube-system get serviceaccount aws-load-balancer-controller \
  -o jsonpath='{.metadata.annotations.eks\.amazonaws\.com/role-arn}{"\n"}'
aws eks list-pod-identity-associations --region "$AWS_REGION" --cluster-name "$CLUSTER_NAME"
kubectl -n kube-system rollout status daemonset/eks-pod-identity-agent
kubectl -n kube-system annotate serviceaccount aws-load-balancer-controller eks.amazonaws.com/role-arn-
kubectl -n kube-system rollout restart deployment/aws-load-balancer-controller
kubectl -n kube-system rollout status deployment/aws-load-balancer-controller
kubectl -n kube-system logs deployment/aws-load-balancer-controller --tail=100
```

새 Pod의 `AWS_CONTAINER_CREDENTIALS_FULL_URI` 환경 변수와 CloudTrail의 새 역할 사용 이력을 확인하고, 기존 Ingress가 정상 조정되는지 검증합니다. 실패하면 기록한 역할 ARN으로 주석을 복원하고 Deployment를 다시 시작해 IRSA로 되돌립니다. `eksctl delete iamserviceaccount`는 실제 서비스 계정도 삭제할 수 있으므로 전환에 사용하지 않습니다. 전환 검증 후 기존 eksctl 스택·공유 IAM 정책·OIDC 공급자의 다른 사용처를 확인한 뒤 별도 정리합니다. 클러스터 복원 시에는 기존 IAM 주석이 복원될 수 있으므로 GitOps 재개 전에 다시 확인합니다.

IRSA 주석이 남아 있는 **전환 전 백업**을 복원해야 한다면 [`restore/load-balancer-pod-identity.yaml`](restore/load-balancer-pod-identity.yaml)을 복원 resource modifier로 사용할 수 있습니다. 이 파일을 복원 작업과 같은 계정·리전의 S3에 업로드하고 복원 metadata `resourceModifiers`에 S3 URI를 지정합니다. 이 규칙은 지정된 서비스 계정의 IRSA 주석만 복원 중 제거합니다. 이미 대상 서비스 계정이 존재하면 비파괴 복원으로 건너뛰며, 백업에 주석이 없으면 remove 패치가 실패할 수 있으므로 전환 후 생성한 백업에는 이 규칙을 쓰지 않습니다. AWS Backup은 패치 실패 시 원본 객체를 복원할 수 있으므로 복원 작업의 modification 실패 및 주석을 반드시 확인합니다. 이 파일은 S3에 자동 업로드되거나 복원 작업에 자동 연결되지 않습니다. [AWS Backup 복원 modifiers](https://docs.aws.amazon.com/aws-backup/latest/devguide/restoring-eks.html)

기존 백업으로 재생성하는 경우 daily 스택이 IAM 권한과 association을 준비하며, AWS Backup이 백업에 포함된 Argo CD·Application·Load Balancer Controller 등 Kubernetes 리소스를 복원합니다. 복원된 Argo CD가 정상 동작하면 재설치나 부모 Application의 재등록은 필요하지 않습니다. 복원 전에 Argo CD를 새로 설치하지 말고, 복원 결과와 IRSA 주석·컨트롤러 권한을 확인한 뒤 GitOps를 재개합니다. 복원된 컨트롤러가 복원 중 동작할 수 있으므로 GitOps와 컨트롤러 실행을 제어하는 방법은 사전 복구시험에서 검증합니다. 백업 없이 처음 구성하는 경우에만 Argo CD 설치와 부모 Application 등록이 별도로 필요합니다. 자세한 내용은 [`k8s/argocd/README.md`](../../k8s/argocd/README.md)를 참고합니다.

공식 근거: [AWS Load Balancer Controller v2.14.0 IAM 정책](https://github.com/kubernetes-sigs/aws-load-balancer-controller/blob/v2.14.0/docs/install/iam_policy.json), [Pod Identity 자격 증명 우선순위](https://docs.aws.amazon.com/eks/latest/userguide/pod-id-minimum-sdk.html), [eksctl 서비스 계정 관리](https://docs.aws.amazon.com/eks/latest/eksctl/iamserviceaccounts.html).

### Karpenter AWS 권한

Daily 스택은 Karpenter 전용 노드 IAM 역할, `${ClusterName}-karpenter` 인스턴스 프로파일, `EC2_LINUX` Access Entry와 컨트롤러 IAM 역할·Pod Identity association을 생성합니다. `karpenter` 네임스페이스의 `karpenter` 서비스 계정을 사용하는 Helm 설정과 연결됩니다. 프로파일 이름을 지정하므로 CLI 배포에는 `CAPABILITY_NAMED_IAM`이 필요하고, Git sync에서도 IAM 생성 권한과 해당 capability를 허용해야 합니다.

컨트롤러는 공식 Karpenter 1.15.2의 EC2 lifecycle·리소스 조회·EKS endpoint 조회 정책을 사용하며 `iam:PassRole`은 전용 노드 역할로 제한합니다. 인스턴스 프로파일은 CloudFormation이 관리하므로 컨트롤러에 프로파일 생성·변경·삭제 권한을 주지 않습니다. 중단 처리 SQS/EventBridge와 Zonal Shift는 구성하지 않았으며 이에 대한 컨트롤러 권한도 없습니다. 노드 역할의 CNI 권한은 기존 관리형 노드의 초기 네트워킹 패턴을 따릅니다.

`KarpenterInstanceProfileName`, `KarpenterNodeRoleArn`, `KarpenterControllerRoleArn`, `KarpenterSecurityGroupId` outputs로 생성 결과를 확인합니다. Kubernetes 설정 및 배포 방법은 [`k8s/argocd/README.md`](../../k8s/argocd/README.md)를 참고합니다. Karpenter가 만든 노드는 CloudFormation 소유가 아니므로 **daily 스택 삭제 전에 NodePool을 비우고 Karpenter 노드 및 launch template 정리를 완료**해야 합니다. 노드가 남아 있으면 역할·프로파일 삭제가 실패하거나 EC2 비용이 계속 발생할 수 있습니다.

공식 근거: [Karpenter 1.15 CloudFormation 권한](https://karpenter.sh/v1.15/reference/cloudformation/), [v1.15.2 upstream 템플릿](https://github.com/aws/karpenter-provider-aws/blob/v1.15.2/website/content/en/preview/getting-started/getting-started-with-karpenter/cloudformation.yaml).

각 node group은 1대이며 업데이트 전략은 `MINIMAL`입니다. 일반 업데이트 surge를 피하는 대신 **단일 역할 노드 업데이트 중 서비스 중단을 허용**합니다. 이것이 전체 AWS 계정 비용 상한이나 Karpenter 추가 노드 상한은 아닙니다.

## 4. 최초 학습 환경 구성

### 최초 학습: 관측용 StorageClass/PVC와 앱을 별도 배포

아래는 **처음부터 새 데이터를 만드는 날에만 사용할 StorageClass 예시**입니다. CloudFormation 리소스가 아니며 템플릿 배포만으로 생성되지 않습니다. 실제 PVC 요청량은 관측 도구별로 정합니다.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: observability-gp3
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  encrypted: "true"
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
```

관측 workload의 **Pod template spec**에는 다음 배치 조건을 사용합니다. Helm values의 경로는 차트마다 다릅니다.

```yaml
nodeSelector:
  workload: observability
tolerations:
  - key: dedicated
    operator: Equal
    value: observability
    effect: NoSchedule
```

앱은 `nodeSelector: {workload: app}`로 배치하고 데이터 PVC를 만들지 않습니다. 노드 로컬 로그·메트릭을 수집하는 Alloy 등 DaemonSet은 **양쪽 노드**에서 실행해야 하므로 관측 노드 전용 selector를 무조건 적용하지 않습니다. 기본 CoreDNS/CSI controller 등 시스템 Pod는 앱 노드에도 배치될 수 있습니다.

## 5. 매일 종료: 데이터 정리가 스택 삭제보다 먼저

템플릿은 **백업 성공을 기다리거나 PVC를 삭제하지 않습니다.** 다음 순서를 별도 운영 절차로 지킵니다.

1. Git 저장, ArgoCD 자동 sync 및 workload 재생성 방지, 데이터 쓰기 중지/flush.
2. EKS composite 백업 생성. `BackupVaultName`과 `BackupRoleArn`은 bootstrap outputs에서 확인.
3. 부모·필요한 모든 EBS 자식 백업 성공 확인. **`COMPLETED`만 검사하지 말고 `MessageCategory`·issues·자식 상태도 확인**하고 recovery point ARN 기록.
4. `namespace/PVC → PV → EBS volume ID → AZ` 목록 기록 후 사용하는 Pod 정상 종료.
5. **CSI와 클러스터가 살아 있을 때** 삭제하기로 한 PVC를 정리. 실제 PV가 `Delete`이면 CSI의 EBS 삭제 완료까지 확인. `Retain`이면 별도 보존/삭제 판단 필요.
6. LB·Ingress 및 Karpenter가 만든 노드 등 스택 밖 자원 정리.
7. 그다음 daily 스택 삭제. bootstrap과 백업·필요한 암호화 키는 유지.
8. 루트 EBS·데이터 EBS·EC2·NAT Gateway·EIP·LB 잔존 여부 확인.

안전상 이 문서에는 포괄적인 PVC/EBS 삭제 스크립트를 넣지 않습니다. **`available`인 EBS 전체를 삭제하거나 CSI finalizer를 강제로 제거하면 안 됩니다.** `DELETE_COMPLETE`도 스택 밖 EBS 정리 완료를 의미하지 않습니다.

정리 대상 식별에 사용할 **읽기 전용 명령**:

```bash
kubectl get pvc -A
kubectl get pv -o custom-columns='PV:.metadata.name,NAMESPACE:.spec.claimRef.namespace,PVC:.spec.claimRef.name,EBS:.spec.csi.volumeHandle,POLICY:.spec.persistentVolumeReclaimPolicy'

# 이 템플릿이 태그한 노드 루트 EBS 확인. PVC 데이터 볼륨 목록이 아닙니다.
aws ec2 describe-volumes --region "$AWS_REGION" \
  --filters "Name=tag:LabCluster,Values=$CLUSTER_NAME" "Name=tag:DiskPurpose,Values=node-root" \
  --query 'Volumes[].{ID:VolumeId,State:State,AZ:AvailabilityZone,Attachments:Attachments}' \
  --output table

# 위 PV 목록에 기록된 데이터 EBS ID를 하나씩 확인합니다.
aws ec2 describe-volumes --region "$AWS_REGION" \
  --volume-ids "${DATA_VOLUME_ID:?PV에서 확인한 데이터 EBS ID를 설정하세요}" \
  --query 'Volumes[].{ID:VolumeId,State:State,AZ:AvailabilityZone,Tags:Tags,Attachments:Attachments}' \
  --output table
```

## 6. 다음 날: 빈 EKS 생성 후 기존 클러스터로 복원

1. 위 daily 템플릿으로 빈 대상 EKS·노드·CSI를 생성합니다.
2. **StorageClass·관측 Helm release·ArgoCD 앱을 먼저 적용하지 않습니다.** AWS Backup은 이미 존재하는 Kubernetes 오브젝트를 덮어쓰지 않습니다.
3. AWS Backup 콘솔에서 전날 **composite recovery point → Restore full EKS cluster → Existing cluster**를 선택하고 방금 생성한 EKS를 지정합니다.
4. 각 EBS 자식 복원에서 bootstrap stack의 `WorkerAvailabilityZone`과 맞는 AZ를 선택합니다. bootstrap outputs의 `BackupRoleArn`을 복원 역할로 사용합니다.
5. 전환 전 IRSA 백업이면 위 resource modifier를 복원 작업에 지정하거나 복원 직후 IRSA 주석 제거·Pod 재시작을 수행합니다. 원본 태그 복사를 선택하고, 복원된 데이터 EBS에 `ebs.csi.aws.com/cluster=true` 태그가 있는지 확인합니다. 현재 `AmazonEBSCSIDriverPolicyV2`는 해당 태그를 사용하므로 누락 시 CSI 작업이 실패할 수 있습니다.
6. 부모·자식 복원 결과와 skipped/failed 오브젝트를 확인하고 PVC `Bound`, Pod `Ready`, 이전 데이터 조회를 검증합니다. 그 후 GitOps를 재개합니다.

기본 Add-on은 CloudFormation이 관리합니다. 복원이 기존 시스템 오브젝트를 건너뛸 수 있으므로 이를 백업 당시의 시스템 설정까지 덮어쓴 것으로 해석하지 않습니다. **최초 원본 삭제 전 복구시험**을 통과해야 합니다.

## 참고: 백업 범위 — 워커 루트 EBS와 관측 데이터 EBS

**현재 템플릿과 EKS composite 백업 계획만으로는 워커의 루트 EBS를 백업하지 않습니다.** 또한 템플릿은 Backup vault와 IAM 역할만 생성하며, 백업 계획·작업을 자동 생성하거나 실행하지 않습니다.

| 대상 | EKS composite 백업 | 일일 스택 재생성 시 |
|---|---|---|
| EKS/Kubernetes 설정 | 지원되는 범위의 설정 백업. 백업 작업을 별도로 실행·검증해야 함 | 일부는 CloudFormation으로 만들고, 나머지는 복원. 기존 오브젝트는 덮어쓰지 않음 |
| 관측 데이터 EBS | 지원되는 EBS CSI 기반 PVC라면 별도 실행한 EKS 백업의 자식 복구 지점에 포함 | 백업에서 새 EBS로 복원하고 PVC 연결을 검증 |
| 두 워커의 **루트 EBS** | **포함되지 않음** | 노드 종료 시 `DeleteOnTermination: true`에 따라 삭제되고, 새 노드가 생성될 때 새 루트 EBS를 생성 |
| 노드 루트의 파일·이미지 캐시·컨테이너 로그 | 별도 백업하지 않으면 보존되지 않음 | 자동 복원되지 않음 |

EKS 백업이 포함하는 영구 데이터는 **지원되는 CSI 드라이버로 PVC에 연결된 저장소**입니다. 노드 루트 디스크는 여기에 해당하지 않습니다. 정확한 자식 복구 지점과 백업 상태를 확인하고, 루트 파일시스템이나 `hostPath`/`emptyDir`에 유일한 데이터를 저장하지 마세요. [AWS Backup EKS 백업 범위](https://docs.aws.amazon.com/aws-backup/latest/devguide/eks-backups.html)

노드 루트 EBS가 꼭 필요하면 EC2 인스턴스 백업이나 해당 EBS 스냅샷을 **별도로** 구성할 수 있지만, 지금 템플릿에는 없습니다. 별도 백업에는 비용이 들고, 백업에서 EC2/볼륨을 복원한다고 새 Managed Node Group의 루트 디스크에 자동으로 붙는 것은 아닙니다. 복원 절차와 노드 부트스트랩을 별도로 설계·검증해야 합니다. [AWS Backup EC2 백업](https://docs.aws.amazon.com/aws-backup/latest/devguide/working-with-supported-services.html)

## 비용 주의

이번 구성에는 기존 public-worker 안에 없던 **NAT Gateway 시간당 요금·처리 GB당 요금·NAT EIP의 공인 IPv4 요금**이 추가됩니다. 워커별 공인 IPv4는 없지만 NAT EIP는 과금됩니다. 이미지 pull·패키지 다운로드 등도 NAT 처리량을 사용합니다. **5만 원 목표를 지킬 수 있다고 보장하지 않으며**, 관측/앱 노드 사양·실제 가동시간·NAT 처리량·백업 namespace와 보존량으로 다시 산정해야 합니다. 기존 문서의 NAT 없는 견적을 그대로 사용하지 않습니다. [VPC/NAT 요금](https://aws.amazon.com/vpc/pricing/)

## 검증 범위와 참고 문서

AWS 배포·실제 노드 가입·백업·복원은 검증하지 않았습니다. 여기의 AWS 명령은 CLI 구문 기준 예시이며 **실제 권한·리전 가용량·API 연결·백업 복원 성공은 첫 배포/복구시험으로 확인**해야 합니다. kubectl 조회도 실제 클러스터 결과를 확인한 예시는 아닙니다. 저장소의 정적 검증 결과는 작업 완료 보고를 확인합니다.

로컬 정적 검증에는 `cfn-lint`, Python 3와 `PyYAML`이 필요합니다. AWS 자격증명이나 실제 배포 없이 실행할 수 있습니다.

```bash
cfn-lint -r ap-northeast-2 -t infra/cloudformation/{bootstrap,daily-eks}.yaml
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s infra/cloudformation/tests -v
```

- [EKS AccessConfig](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-eks-cluster-accessconfig.html), [UpgradePolicy](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-eks-cluster-upgradepolicy.html)
- [EKS endpoint](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoint.html), [Launch Template 제한](https://docs.aws.amazon.com/eks/latest/userguide/launch-templates.html)
- [EBS CSI](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html), [IAM·복원 태그 주의](https://docs.aws.amazon.com/eks/latest/best-practices/identity-and-access-management.html)
- [AWS Backup 리전 설정](https://docs.aws.amazon.com/cli/latest/reference/backup/update-region-settings.html), [EKS 백업](https://docs.aws.amazon.com/aws-backup/latest/devguide/eks-backups.html), [EKS 복원](https://docs.aws.amazon.com/aws-backup/latest/devguide/restoring-eks.html)
