# 4인 개발·Observability 학습 계획 / 인터뷰 명세
## Metadata
- Profile: standard; 4 rounds; greenfield learning design.
- Final ambiguity: 9%; threshold: 20%. Heuristic clarity assessment, not statistical confidence.
- Context snapshot: .omx/context/team-dev-observability-learning-20261109T002641Z.md
- Initial-context summary gate: not_needed.
- Status: requirements clarified, planning-only. No execution handoff authorized.

## Intent / Desired Outcome
[from-user] 완성도 높은 서비스보다 각 도구의 기본 사용 경험이 우선이다.
개발에서는 React–Spring Boot 연결을 이해하고, 나머지에서는 기능·동작 원리·설정 방법을 이해한다.
4인이 공동 환경을 사용한다. 날짜마다 조작 담당을 바꾸고 나머지는 함께 검증한다.

## Clarity
| Dimension | Score | Evidence / remaining gap |
|---|---:|---|
| Intent | 1.00 | 기능과 원리, 프런트–백 연결 명시 |
| Outcome | .95 | 일별 실습·설명·검증 결과, 구체 앱은 제안 |
| Scope | .95 | 제시된 9개 묶음 = 9일 |
| Constraints | .65 | 일 4–5시간, 약 5만원; 리전·가동 일수·정확한 사양 미정 |
| Success | .90 | 공동 검증, 원리 설명·설정 변경 확인 기준을 계획에서 구체화 |
Weighted ambiguity = 1 - (.30*1 + .25*.95 + .20*.95 + .15*.65 + .10*.90) = .085.

## In-Scope
- React; Spring Boot; Helm/Kustomize; CNI; KEDA/Karpenter; GitHub Actions/ArgoCD; Prometheus/Alertmanager; Tempo/Loki/Alloy; Grafana.
- 9일 × 4–5시간. 기술 묶음은 유지.
- GitHub 소스 협업과 SSH 원격 접속 역할을 구분한 제안.
- 공동 환경, 순환 역할, 일별 확인 실습, 비용·준비 위험 정리.

## Non-goals
- 이번 작업에서 코드 구현, 패키지 설치, 계정 접근, AWS 생성·설정·과금 작업 금지.
- 운영 수준 HA·보안·성능 보장, 복잡한 업무 앱 완성은 목표가 아님(목적에 따른 계획상 제외).
- 기본 예제 앱에 DB·로그인·복잡한 UI를 필수로 넣지 않음.
- 기술 하나를 하루 만에 숙련한다고 약속하지 않음.

## Decision Boundaries
- 계획 내 추천과 대안·학습 완료 기준을 작성하는 범위만 허용.
- 2대는 사용자의 예상이지 고정 요구가 아님. 추가 노드의 일시 사용은 학습 시 허용 가능하다는 선호.
- 약 5만원은 목표이며 소폭 초과 가능하나 숫자로 된 상한 또는 지출 승인이 아님.
- 상시 EKS는 기본안에서 제외. 리전·사양·Karpenter 실제 실습 경로·실제 예산 초과·권한·노출 범위는 실행 전 확정해야 함.
- 후속 구현·자동 실행 모드로 넘기지 않음. 사용자 요청 시 별도 계획 검토 가능.

## Constraints / Assumptions
- 기존 코드·README·docs 없는 빈 작업 공간(.omx만 존재).
- [from-user] 9묶음 각각 하루, 하루 4–5시간.
- [from-user] 예산 목표 약 5만원, 소폭 초과 가능; Karpenter로 잠깐 EC2 증가 가능.
- [planning assumption] 기본 Git·터미널·컨테이너 개념은 알고 시작. 아니라면 별도 준비 시간이 필요하며 9일 안에 숨겨 넣지 않는다.
- [planning assumption] 학습시간 밖에는 가능한 자원을 줄이는 비용 우선 실습. 사용자 후속 확인: 주말을 제외한 학습은 약 2주에 걸쳐 진행. EKS의 24시간 유지 비용을 우려.
- 공통 준비는 9개 주제와 별개 비용/시간으로 명시. 당일 4–5시간에 AWS/IAM/클러스터 준비를 무조건 포함할 수 있다고 주장하지 않는다.

## Proposed Environment (recommendation, not provisioned)
1. GitHub가 코드·매니페스트의 기준. 개인 브랜치→PR→검토→병합.
2. SSH는 공동 EC2 작업·점검 경로. 각자 키/계정을 분리하고 소스 변경은 Git에 남긴다.
3. 동일 공유 디렉터리에서 4명 동시 편집은 피한다. 로컬 또는 분리 작업 디렉터리에서 개발.
4. 일반 실습: EC2 자체 관리 Kubernetes, CNI의 노드 간 경로 관찰 시 2노드 후보. HA가 아니다.
5. 상시 EKS는 예산 때문에 기본안에서 제외한다. Karpenter를 위해 단기 EKS를 자동으로 추가하지 않는다.
6. Karpenter 실제 노드 생성은 미확정: kOps 자체 관리 지원 경로(추가 준비) 또는 당일 생성·삭제하는 선택적 EKS 실습(추가 비용·시간)을 비교해 실행 전에 결정한다. EKS 경로는 이번 기본 예산/일정에 포함 확정하지 않는다.
7. 기본안은 EC2 자체 관리 클러스터를 학습시간에 가동하고 야간·주말에는 중지하는 방식이다. 기존 kubeadm 클러스터가 Karpenter를 바로 지원한다고 가정하지 않는다. 재개 후 노드·네트워크·볼륨 상태를 점검한다.
8. EC2 한 대에 모든 관측 도구를 항상 켜놓는 대신, 당일 필요한 스택만 사용하고 보존기간·샘플 데이터를 작게 잡는 계획. 정확 사양은 리소스 요청량 확인 후 결정.

## 9-Day Proposed Curriculum
| Day | Bundle | Practice / principle | Completion evidence |
|---|---|---|---|
| 1 | React | 컴포넌트·상태·이벤트, fetch와 비동기, 임시 JSON/mock으로 작은 조회 화면; 브라우저와 API 서버 역할 구분 | 요청 URL·응답 JSON·로딩/오류 상태를 Network 탭으로 설명 |
| 2 | Spring Boot | Controller→Service, JSON 직렬화·HTTP 상태, Day1 연결; origin·CORS·프록시의 차이 | 브라우저→백엔드→응답→화면 흐름과 의도적 연결 오류 원인 설명 |
| 3 | Helm/Kustomize | 같은 앱을 대상으로 Helm 템플릿/values vs Kustomize base/overlay 비교; 렌더 결과와 선언 상태 | 환경별 설정을 바꾸고 생성 매니페스트 차이 및 적용 결과 확인 |
| 4 | CNI | Pod IP·노드 간 패킷 경로, Service 네트워킹과 CNI 역할 차이; 선택 플러그인의 NetworkPolicy 지원 확인 | 서로 다른 노드 Pod 통신 확인, 정책 지원 시 차단/허용 전후 설명 |
| 5 | KEDA/Karpenter | KEDA는 이벤트 기반 워크로드 확장, Karpenter는 수용할 노드 공급; KEDA는 준비된 이벤트원으로 실습. Karpenter 실제 AWS 실습 경로는 미확정 | KEDA 확장 관찰, Karpenter의 노드 공급 원리·설정 설명. 실제 EC2 자동 생성 검증은 별도 경로 확정 후에만 완료로 인정 |
| 6 | GitHub Actions/ArgoCD | 테스트/이미지 빌드·태그→Git 매니페스트 변경→Argo CD 동기화; CI와 CD 책임 분리 | PR→병합→배포·Git revert 기반 복구 흐름을 재현/설명 |
| 7 | Prometheus/Alertmanager | scrape·시계열·레이블·PromQL·rule 평가·알림 routing/grouping/silence | 안전한 데모 알림 발생·해제 및 의도한 수신 경로 확인 |
| 8 | Tempo/Loki/Alloy | Alloy 수집·전송, Loki 로그·Tempo trace 저장, trace/span 및 context 전파 | 백엔드 계측 후 요청 하나의 trace와 관련 로그를 연결; 자동 계측 없는 trace 생성은 가정하지 않음 |
| 9 | Grafana | datasource·dashboard·탐색, metrics→logs→traces 상관관계 | 의도적 오류/지연 상황에서 증거를 따라 원인 설명; 각 도구 책임 회고 |

### Daily Rhythm / Roles
- 45분: 기능·왜 필요한지·동작 흐름.
- 30분: 설정 읽기와 예측.
- 105분: 실습·설정 변경·관찰.
- 45분: 안전한 실패 시나리오 및 검증.
- 15분: 설정 diff·스크린샷·원리·실패 원인 정리.
- 총 4시간. 남는 0–60분은 준비/문제 해결 버퍼.
- 조작자·설정 검토자·검증자·기록자를 순환. 9일이므로 담당 횟수는 2~3회로 배분.

### Explicit Prerequisites
- Day3 이전 Kubernetes 준비 필요; 클러스터 설치 자체가 별도 준비 범위.
- Day4 사용 CNI와 정책 지원을 사전 확인. 공유 클러스터에서 무계획 플러그인 교체 금지.
- Day5 Karpenter 실제 실습은 경로 미확정으로 남긴다. 수행하려면 AWS/IAM/노드 부트스트랩·네트워크 준비가 필요. KEDA 이벤트원 샘플과 컨트롤러 사전 준비. 학습자는 설정과 작동을 검증한다. 준비가 없으면 4–5시간 내 두 기술의 실제 실습 완료는 위험.
- Day6 저장소·이미지 registry·접근 권한과 이미지 태그 변경 경로 준비.
- Day7 metrics endpoint, Day8 애플리케이션 trace 계측 및 trace ID 로그 기록 필요.
- Day9 이전 Grafana를 임시 확인 UI로 쓰는 것은 가능하나 대시보드 학습은 Day9.

## Cost Boundary / Evidence
[from-research] Kubernetes는 단일 노드 가능. 2노드는 노드 간 통신 관찰에 유용하다는 설계 추론.
https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/create-cluster-kubeadm/
[from-research] Karpenter 공식 AWS 시작 가이드는 EKS/IAM 연동 경로:
https://karpenter.sh/docs/getting-started/getting-started-with-karpenter/
[from-research] self-managed도 불가능한 것은 아님; kOps 공식 지원 경로가 있으나 별도 전제:
https://kops.sigs.k8s.io/operations/karpenter/
[from-research] EKS standard support control plane $0.10/cluster-hour; 216h=$21.60, 5h=$0.50, 컴퓨트 등 별도:
https://aws.amazon.com/eks/pricing/
[from-research] public IPv4 $0.005/address-hour; NAT 별도 시간/처리량 과금:
https://aws.amazon.com/vpc/pricing/
[from-research] Argo CD는 Git의 선언 상태를 사용:
https://argo-cd.readthedocs.io/en/stable/
- 공식 문서 확인: 2026-11-09. 버전은 실행 직전에 호환성을 확인해 고정.
- 총액 계산식: EC2 instance-hours + EBS GB-month/추가 IOPS + IPv4-hours + EKS-hours + NAT/LB + 데이터 전송/로그·저장 + 세금·환율.
- 5만원 보장 불가. 리전·사양·캘린더 가동시간·잔존 디스크·IP 미정.
- NAT/LB를 무조건 추가하지 않으며 접근 편의와 보안 요구를 검토한다. 무단 공개 포트로 비용을 아끼지 않는다.
- EC2 중지만으로 EBS·IPv4·EKS 비용까지 중단되지 않는다. 실습 종료별 잔존 자원 목록과 정리 절차가 필요.
- EKS 일시 구성에는 생성/정리 대기 비용도 포함; 정확히 실습 5시간만 청구된다고 보장하지 않는다.

## Testable Acceptance Criteria (for plan, not implementation)
- 9개 원래 묶음을 누락 없이 9일로 표시.
- 일 4–5시간 타임박스와 준비 시간 위험을 명시.
- 각 날짜에 원리·설정 변경·관찰 결과/설명 기준 존재.
- 프런트–백 연결에 HTTP 요청·JSON·오류 경로 포함.
- 공동 환경 순환 방식, GitHub/SSH 역할, 공유 편집 충돌 방지 포함.
- 비용 목표와 불확실성·추가 과금 요소를 명시하고 지출/실행하지 않음.
- Kubernetes Pod 확장과 노드 확장을 구분.
- 기존 앱·AWS 계정 조작 없이 계획 아티팩트만 생성.

## Pressure Pass / Exposed Assumptions
- Round1의 '도구 직접 경험'을 Round2에서 '한 명만 조작해도 성공인가'로 재검증.
- 해소: 전원이 매번 설치할 필요 없음; 공동 검증과 담당자 순환이 기준.
- Round3에서 '하루 하나'는 개별 제품이 아니라 사용자가 대시로 나눈 9묶음임을 확정.
- Round4의 'Kubernetes는 EC2 2대 필수'는 사용자 선호/가설로 기록하고 공식 문서로 교정.
- SSH vs GitHub는 원격 접속 vs 소스 이력/협업으로 서로 배타적이지 않음.
- 예산 목표는 지출 승인이나 정확 상한이 아님.

## Docs / Terminology Ledger
- 사용자 제공 AGENTS.md와 설치된 deep-interview, best-practice-research 지침 확인.
- 현재 디렉터리에 기존 README/docs/앱/관련 스냅샷 없음; 적용 상위 경로 AGENTS.md 없음.
- Brownfield code/doc mismatch 없음.
- 제품 원리 설명에서 CNI/Service, KEDA/Karpenter, Alloy/storage/backend 책임을 혼동하지 않음.
- Durable public docs/ADR 추천은 opt-in. 인터뷰 내용은 .omx 내부 아티팩트에만 저장.

## Condensed Transcript
1. 목적? → [from-user] 각 도구의 기본 사용 경험(tool-tour).
2. 직접 경험의 완료 기준? → [from-user] 공동 환경에서 담당자 순환(rotate).
3. 기간·하루 시간? → [from-user] 9개 대시 묶음 각각 하루, 4–5시간. 개발은 FE-BE 연결, 나머지는 기능·원리·설정.
4. 비용·환경 결정 경계? → [from-user] EC2 2대 예상, Karpenter 잠깐 증설 허용, 약 5만원 선호·조금 초과 가능.

## Stop / Handoff
이번 산출물은 계획이며 여기서 종료. 다음 workflow 실행하지 않음.
- 추가 아키텍처 검토를 원할 때: $ralplan (이 명세 입력, planning-only 경계 유지).
- 미래 명시적 구현 요청 시에만: $ultragoal / $autopilot; 조정 가치가 있을 때 $team.
- 현재 $autoresearch/$performance-goal에 해당하는 연구 evaluator/최적화 요구 없음.

## 후속 수정: EKS 상시 유지 제외 (2026-11-09)
- [from-user] 약 2주 달력 기간에 걸쳐 주말은 학습하지 않음. 중지 불가능한 EKS 상시 유지 비용 우려.
- [from-research] EKS Stop/Pause API 없음. 워커 축소/중지는 컨트롤 플레인 요금을 없애지 않음.
  https://docs.aws.amazon.com/eks/latest/APIReference/API_Operations.html
  https://docs.aws.amazon.com/eks/latest/userguide/delete-cluster.html
- 표준 지원 EKS 14일 = 14*24*$0.10 = $33.60 (컨트롤 플레인만). EC2/EBS/IPv4/세금 별도. 환율 미확인으로 원화 확정값은 제시하지 않음.
- 정정: EKS 단기 실습도 비용·준비 시간이 있으므로 기본안에 암묵적으로 포함하지 않는다.
- 남은 판단: Karpenter 실제 노드 생성은 kOps 추가 준비 vs 단기 EKS 선택 실습 중 실행 전 결정. 개념 학습을 실제 실습 완료라고 표시하지 않는다.
