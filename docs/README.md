# 작은 게시판

글을 쓰고, 익명 댓글과 좋아요를 남기는 연습용 게시판입니다. SayScene에서 사용한 React·TypeScript·Vite와 Java·Spring Boot·Redis를 그대로 사용합니다. 로그인과 수정·삭제는 없습니다. 글 목록은 한 페이지에 5개씩 표시합니다. 연필 버튼을 누르면 글쓰기 전용 화면이 열리고, 오른쪽 위 취소 버튼으로 돌아갈 수 있습니다.

## 실행

Node.js 22.12 이상, Java 21, Maven, Docker가 필요합니다. 아래 명령은 저장소 최상위 폴더에서 시작하고, 서버들은 각기 다른 터미널에서 실행합니다.

```bash
# 저장소 최상위 폴더에서 Redis 시작
docker compose up -d

# BE 시작
cd be
mvn spring-boot:run

# FE 시작
cd fe
npm ci
npm run dev
```

브라우저에서 Vite가 표시하는 주소(기본 `http://127.0.0.1:5173`)를 엽니다. FE의 `/api` 요청은 BE의 `http://127.0.0.1:8080`으로 전달됩니다. BE는 `127.0.0.1:6380`의 Redis에 접속합니다. 포트를 바꾸려면 `REDIS_HOST`, `REDIS_PORT`, `PORT` 환경변수를 지정합니다.

Redis를 끌 때는 `docker compose down`을 실행합니다. 이 명령은 데이터를 남깁니다. **저장한 글까지 지울 때만** `docker compose down -v`를 실행합니다. Redis 데이터는 `board-redis` 볼륨에 보관됩니다.

## 기능과 코드 읽기

| 파일 | 읽어 볼 표현 |
|---|---|
| `fe/src/App.tsx` | `.map()`, `?.`, `??`, `useState`, `useEffect`, `async/await` |
| `be/src/main/java/com/example/board/BoardController.java` | `record`, `@GetMapping`, `@PostMapping`, `@RequestBody` |
| `be/src/main/java/com/example/board/BoardStore.java` | `stream().map().toList()`, `var`, `Map.of()`, Redis `increment()` |

API는 글 목록 `GET /api/posts`, 글 작성 `POST /api/posts`, 글 상세 `GET /api/posts/{id}`, 댓글 `POST /api/posts/{id}/comments`, 좋아요 `POST /api/posts/{id}/likes`입니다. 제목은 최대 100자, 본문은 2,000자, 댓글은 500자까지 입력할 수 있습니다. 좋아요는 같은 사람이 여러 번 누를 수 있습니다.

## 확인

```bash
(cd be && mvn test)
(cd fe && npm test && npm run build)
```

이 프로젝트는 비공개 연습용입니다. 인터넷에서 접속 가능한 곳에 올리면 주소를 아는 누구나 글과 댓글을 쓸 수 있습니다.

## EKS 실습 준비

`fe/Dockerfile`과 `be/Dockerfile`은 각각 실행 이미지를 만듭니다. `k8s/`에는 `practice-board` 네임스페이스 안에서 FE·BE·Redis를 실행하고 ALB로 접속하는 설정이 있습니다. 지금 들어 있는 `example.invalid` 이미지 주소는 **반드시 실제 이미지 레지스트리 주소로 바꿔야 하는 자리표시자**입니다.

1. FE·BE 이미지를 빌드해 EKS 노드가 읽을 수 있는 레지스트리(ECR 등)에 올립니다.
2. `k8s/kustomization.yaml`의 두 `newName`과 `newTag`를 올린 이미지에 맞춥니다.
3. 적용 전 `kubectl config current-context`로 대상 클러스터를 확인하고 `kubectl kustomize k8s`로 결과를 봅니다.
4. 적용할 때 `kubectl apply -k k8s`를 사용합니다. FE·BE·Redis와 서비스가 `practice-board` 네임스페이스에 생깁니다.
5. 내부 접속 시험에는 `kubectl -n practice-board port-forward svc/practice-board-web 8088:80`을 쓰고 `http://127.0.0.1:8088`로 접속할 수 있습니다.
6. ALB 주소는 `kubectl -n practice-board get ingress practice-board`의 `ADDRESS`에서 확인합니다.

EKS에서 BE는 `127.0.0.1` 대신 `practice-board-redis:6379`에 접속합니다. FE의 Nginx는 `/api` 요청을 `practice-board-api:8080`으로 전달합니다. EKS Redis는 실습을 단순하게 하기 위해 영구 볼륨을 쓰지 않습니다. **Redis Pod가 다시 만들어지면 글·댓글·좋아요 데이터가 사라집니다.**

`k8s/40-ingress.yaml`은 `ingressClassName: alb`와 `internet-facing`으로 **별도 공개 ALB**를 요청합니다. HTTP 80의 모든 경로를 FE 서비스로 보내고 `/`로 FE 상태를 검사합니다. FE 안의 Nginx가 `/api`만 BE로 전달합니다. 이 설정은 AWS Load Balancer Controller 또는 대응하는 EKS ALB 환경, ALB용 서브넷 설정, 이미지 pull 권한이 있어야 동작합니다. 도메인·인증서가 없으므로 HTTPS는 설정하지 않았습니다. 주소를 공유하지 않아도 ALB는 인터넷에서 접근 가능하며, 생성되는 동안 ALB 비용이 발생할 수 있습니다.

**현재 실습 클러스터 확인 결과(2026-11-10):** AWS CLI의 기본 IAM 사용자로 `final-sprint-cluster`를 확인했고 노드는 `amd64`입니다. `ecr:DescribeRepositories` 권한이 없어 실제 ECR 저장소 주소는 확인하지 못했습니다. 현재 클러스터에는 `alb` IngressClass와 AWS Load Balancer Controller Deployment가 보이지 않고 EKS Auto Mode 로드밸런싱도 꺼져 있습니다. 따라서 **ALB 컨트롤러를 준비하기 전에는 Ingress를 적용해도 ALB 주소가 생성되지 않습니다.** 이 상태는 배포 전 다시 확인해야 합니다.

이미지 빌드 시 노드 아키텍처에 맞춰 `--platform linux/amd64`를 사용합니다. ECR 저장소 주소를 `BE_ECR_URI`, `FE_ECR_URI` 환경변수에 설정하고 로그인한 뒤 아래처럼 빌드·푸시합니다. 같은 주소와 태그를 `k8s/kustomization.yaml`에 적습니다.

```bash
docker buildx build --platform linux/amd64 -t "${BE_ECR_URI}:v1" --push ./be
docker buildx build --platform linux/amd64 -t "${FE_ECR_URI}:v1" --push ./fe
```

되돌릴 때는 먼저 대상 클러스터를 확인한 뒤 `kubectl delete -k k8s`로 이 실습 리소스를 제거할 수 있습니다. 이 명령은 `practice-board` 네임스페이스와 안의 데이터도 삭제합니다. 이미지를 올린 레지스트리의 이미지까지 지우지는 않습니다. 실제 클러스터 적용과 이미지 업로드는 이 저장소를 준비하는 작업에 포함되지 않습니다.
