## 결론

**CloudFormation으로 빈 EKS를 재생성한 뒤, AWS Backup에서 그 클러스터로 복원하는 방식이 가능합니다.**

서울 리전 기준으로 아래 예시를 계산하면:

- **9일 모두 EKS 사용:** 약 **$36.17**, 예시 환율·부가세 적용 시 **약 55,700원 + 추가 사용료**
- **React·Spring Boot는 로컬에서 하고 나머지 7일만 EKS 사용:** 약 **$28.02**, 같은 조건으로 **약 43,100원 + 추가 사용료**

이는 **명시한 구성의 계산값**이지 확정 청구액은 아닙니다. 특히 하루 생성·복원·백업·삭제 시간을 **1시간으로 가정**했으며, 실측하지 않았습니다.

아래는 **2026-11-09 공식 문서·서울 리전 공개 가격표**를 확인한 결과입니다. AWS 작업은 실행하지 않았습니다.

---

## 1. 복구 가능한 범위

복원할 대상은 **Kubernetes 설정과 영구 데이터**입니다. 실행 중 메모리나 기존 Pod IP까지 그대로 재개하는 것은 아닙니다.

AWS Backup은 EKS의 Kubernetes 리소스와 지원되는 PVC 저장소를 묶어 백업합니다. **컨테이너 이미지, VPC·서브넷, 노드 로컬의 임시 데이터는 별도로 관리해야 합니다.** 서울 리전에서도 지원됩니다. [백업 범위](https://docs.aws.amazon.com/aws-backup/latest/devguide/eks-backups.html), [지원 리전](https://docs.aws.amazon.com/aws-backup/latest/devguide/backup-feature-availability.html)

따라서 저장 방식은 다음처럼 제한하는 것이 좋습니다.

- 앱·관측 데이터: **EBS CSI 기반 PVC**
- 코드·Helm values·Kustomize 설정: **Git**
- 컨테이너 이미지: 삭제하지 않는 이미지 저장소
- `emptyDir`, `hostPath`, 컨테이너 내부 파일: **보존 대상에서 제외**

---

## 2. CloudFormation 구성

**계속 남기는 기반 스택과 매일 삭제할 스택을 분리**합니다.

| 구분 | 포함할 리소스 | 학습 종료 후 |
|---|---|---|
| 기반 스택 | VPC·서브넷·보안 그룹, Backup vault, 필요한 KMS 키, 백업·복원 IAM 역할 | 유지 |
| 일일 클러스터 스택 | EKS, Managed Node Group, 기본 Add-on, 클러스터별 권한 연결 | 삭제 |
| Kubernetes 동적 리소스 | PVC로 생성한 EBS, Karpenter 노드, LoadBalancer 등 | 백업 확인 후 별도 정리 |

**Backup vault와 암호화 키를 일일 스택에 넣으면 안 됩니다.** 클러스터와 함께 백업까지 잃는 구조를 피해야 합니다.

또한 PVC가 동적으로 만든 EBS나 Karpenter가 만든 EC2가 **CloudFormation 스택 삭제만으로 모두 정리된다고 가정하면 안 됩니다.**

### 최초 준비에서 필요한 설정

1. **EKS 인증 모드**
   - `AccessConfig.AuthenticationMode`를 `API` 또는 `API_AND_CONFIG_MAP`으로 설정합니다.
   - AWS Backup이 Access Entry를 생성할 수 있어야 합니다. [CloudFormation 설정](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-eks-cluster-accessconfig.html)

2. **백업·복원 역할**
   - `AWSBackupServiceRolePolicyForBackup`
   - `AWSBackupServiceRolePolicyForRestores`
   - AWS Backup 서비스가 역할을 Assume할 수 있는 신뢰 정책과 필요한 KMS 권한도 준비합니다. [서비스 역할 문서](https://docs.aws.amazon.com/aws-backup/latest/devguide/iam-service-roles.html)

3. **기본 환경**
   - AWS Backup 설정에서 EKS 보호 활성화
   - EBS CSI Add-on 설치
   - 원본·복원 대상의 Kubernetes 버전 동일하게 유지
   - 복원할 EBS의 AZ에 워커 배치
   - Git·이미지 저장소·필요한 IAM 역할 유지

---

## 3. 매일 종료할 때의 정확한 순서

### ① 변경사항 저장 및 쓰기 정지

- 코드·설정을 Git에 저장합니다.
- **ArgoCD 자동 동기화를 중지**하고, 복원 후에도 자동 동기화가 바로 시작되지 않도록 합니다.
- 앱 쓰기와 관측 데이터 수집을 멈추거나 flush합니다.

EBS 스냅샷이 여러 앱의 데이터를 하나의 원자적 시점으로 보장하는 것은 아닙니다. 디스크에 반영되지 않은 데이터까지 보존하려면 애플리케이션 일관성 처리가 필요합니다. [EBS 스냅샷 주의사항](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-creating-snapshot.html)

### ② EKS 전체 백업

AWS Backup 콘솔에서:

1. **Protected resources → Create on-demand backup**
2. Resource type: **Amazon EKS**
3. 학습 클러스터 선택
4. 기반 스택의 Backup vault 선택
5. 백업 역할 선택
6. 보존 기간 설정 — 아래 비용 계산에서는 **각 백업 14일**
7. 백업 시작

CLI에서는 `aws backup start-backup-job`에 해당합니다.

### ③ 백업 성공 검증

다음을 모두 확인합니다.

- 부모 백업 작업 성공
- EKS 설정과 **모든 필요한 EBS 자식 백업 성공**
- `Partial`, `Completed with issues` 여부 확인
- Composite recovery point ARN 기록

**`COMPLETED` 문자열 하나만 보고 삭제하면 안 됩니다.** API에서는 일부 문제가 있어도 `COMPLETED`로 표시될 수 있어 `MessageCategory`와 자식 작업을 함께 확인해야 합니다. [백업 작업 조회](https://docs.aws.amazon.com/cli/latest/reference/backup/list-backup-jobs.html)

**처음 도입할 때는 원본 삭제 전에 별도 복구시험 1회를 통과하는 것을 권합니다.**

### ④ 자원 정리

백업 검증 후:

1. LoadBalancer Service·Ingress 등 외부 자원 정상 해제
2. Karpenter 생성 노드 등 스택 밖 자원 정리
3. 일일 CloudFormation 스택 삭제
4. 불필요해진 원본 데이터 EBS 정리
5. EC2·EBS·IP·LB 등 잔존 자원 확인

이 순서가 없으면 클러스터를 지워도 로드밸런서 등이 남을 수 있습니다. [EKS 삭제 절차](https://docs.aws.amazon.com/eks/latest/userguide/delete-cluster.html)

---

## 4. 다음 날 복원하는 순서

### ① CloudFormation으로 빈 클러스터 생성

기반 스택을 참조해 다음을 생성합니다.

- EKS
- Managed Node Group
- 네트워킹·DNS·EBS CSI Add-on
- 접근 권한과 클러스터별 IAM 연결

**앱을 Helm이나 ArgoCD로 먼저 배포하지 않습니다.** AWS Backup은 이미 존재하는 Kubernetes 오브젝트를 덮어쓰지 않기 때문입니다.

### ② AWS Backup에서 기존 클러스터로 복원

콘솔에서:

1. **Backup vaults → 전날 Composite recovery point**
2. **Restore**
3. **Restore full EKS cluster**
4. 대상: **Existing cluster**
5. CloudFormation으로 방금 생성한 EKS 선택
6. 각 EBS 볼륨의 복원 AZ 지정
7. 복원 역할 선택
8. 복원 실행

이 경로는 CLI 메타데이터의 `clusterName`과 `newCluster: "false"`에 해당합니다. **데이터까지 복원하려면 자식 EBS 복원 설정도 필요**하므로 두 필드만 넣는 예제를 완전한 복구 자동화로 보면 안 됩니다.

같은 이름으로 재생성해도 IRSA의 새 OIDC 신뢰 관계를 확인해야 합니다. 복원 완료 후에는 **PVC `Bound`, Pod `Ready`, 기존 파일·대시보드·로그 조회**를 검증한 뒤 GitOps를 재개합니다. [공식 복원 절차·제약](https://docs.aws.amazon.com/aws-backup/latest/devguide/restoring-eks.html)

---

## 5. 비용 계산 조건

아직 사양이 확정되지 않았으므로 다음 구성으로 계산했습니다.

| 항목 | 계산 가정 |
|---|---|
| 리전 | 서울 `ap-northeast-2` |
| EKS | 표준 지원, 일반 Managed Node Group |
| 사용 시간 | 9일 × 하루 6시간 = **54시간** |
| 하루 6시간 | 학습 5시간 + 생성·복원·백업·삭제 1시간 가정 |
| 워커 | Linux On-Demand `m6i.large` 2대 |
| 워커 사양 | 각 2 vCPU / 8 GiB RAM |
| gp3 | 루트 20 GiB × 2 + 데이터 PVC 합계 20 GiB |
| 공인 IPv4 | 워커당 1개, 가동 중에만 사용 |
| Namespace | 매번 **9개** 백업·복원 가정 |
| 작업 횟수 | 백업 9회, 복원 8회 |
| 백업 보관 | 각 백업 생성 후 14일 |
| 제외 구성 | NAT Gateway·LB·별도 Bastion·유료 EKS 부가기능 없음 |

Namespace 9개는 기본 4개와 `app`, `monitoring`, `argocd`, `keda`, `karpenter`를 가정했습니다. **실제 비용은 매회 백업·복원하는 namespace 수에 따라 달라집니다.**

데이터 스냅샷은 매번 실제 저장 데이터 20 GiB로 보수적으로 계산했습니다. 새 볼륨으로 복원하므로 **모든 백업이 하나의 증분 체인을 공유한다고 가정하지 않았습니다.**

### 서울 리전 단가와 산식

| 항목 | 단가 | 계산 | 비용 |
|---|---:|---|---:|
| EKS | $0.10/시간 | 54 × 0.10 | **$5.40** |
| EC2 2대 | $0.118/대·시간 | 108 × 0.118 | **$12.744** |
| 공인 IPv4 | $0.005/IP·시간 | 108 × 0.005 | **$0.54** |
| gp3 60 GiB | $0.0912/GB·월 | 60 × 54/720 × 0.0912 | **$0.4104** |
| EKS 백업 생성 | $0.11/namespace·회 | 9회 × 9개 × 0.11 | **$8.91** |
| EKS 복원 | $0.055/namespace·회 | 8회 × 9개 × 0.055 | **$3.96** |
| EBS 스냅샷 보관 | $0.05/GB·월 | 9 × 20 × 14/30 × 0.05 | **$4.20** |
| EKS 설정 백업 보관 | $0.011/GB·월 | 회당 약 20 MiB 가정 | **약 $0.001** |
| CloudFormation | AWS 리소스 관리 추가 요금 없음 | — | **$0** |
| **산정 소계** | | | **약 $36.17** |

월 단위 항목은 **30일·720시간 기준으로 비례 계산**했습니다.

단가 출처: [서울 EC2·EBS 공식 가격표](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/ap-northeast-2/index.csv), [서울 AWS Backup 공식 가격표](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSBackup/current/ap-northeast-2/index.json), [EKS](https://aws.amazon.com/eks/pricing/), [IPv4](https://aws.amazon.com/vpc/pricing/), [CloudFormation](https://aws.amazon.com/cloudformation/pricing/).

### 원화 환산 예시

**실시간 환율이 아닌 계산용 환율 `1달러=1,400원`, 부가세 10%를 가정**하면:

```text
약 $36.1653 × 1,400원 × 1.10
= 약 55,700원
```

이 금액에는 마지막 학습일 이후에도 남는 **각 백업의 14일 보관 비용**이 포함됩니다.

---

## 6. 추가 비용과 최종 판단

위 소계에 다음은 추가됩니다.

- 최초 복구시험: 9개 namespace 복원료 **$0.495**와 시험용 EKS·EC2 시간
- Karpenter 추가 노드
- 이미지 저장소, 데이터 전송, CloudWatch, KMS 등 사용료
- 복원 지연·실패·재시도로 늘어난 시간

같은 구성에서 **매일 1시간씩 더 걸리면 9일 합계 약 $3.18 추가**, namespace가 매번 하나 더 포함되면 **약 $1.43 추가**입니다.

### 이번 학습에 맞춘 권고

**9일 전부 EKS를 사용하면 5만 원 목표를 넘길 가능성이 높으므로, 약 6만~7만 원의 계획 예산이 현실적입니다.** 이는 보장 상한은 아닙니다.

반면 **React·Spring Boot 이틀은 로컬에서 하고, 나머지 7일만 EKS를 사용**하면 동일한 조건의 산정 소계는:

- **약 $28.02**
- 위 예시 환율·부가세로 **약 43,100원**
- 복구시험·추가 노드·기타 사용료 별도

따라서 **“개발 2일은 로컬, 인프라·관측 7일은 EKS 삭제·복원”**이 현재 예산에 더 가까운 안입니다. 단, 자동화를 만들기 전에 **한 번의 실제 복구시험으로 복구 시간과 데이터 보존을 검증해야** 하루 4~5시간 학습 일정에 들어갈지 판단할 수 있습니다.
