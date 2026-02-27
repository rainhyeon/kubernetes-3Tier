# kuberenete-3Tier 구축

[파일 구성도]
```
controlplane:~/kubernetes-3Tier$ tree
.
|-- README.md
|-- k8s
|   |-- 00-namespace.yaml    # namespace 생성 파일
|   |-- 10-db.yaml           # DB(Secret, Deployment, Service) - 5432
|   |-- 20-was.yaml          # WAS(ConfigMap, Deployment, Service) - 8080
|   `-- 30-web.yaml          # WEB(Deployment, Service) - 80
|-- was
|   |-- Dockerfile           # python 환경에서 빌드
|   |-- app.py               # Flask API
|   `-- requirements.txt     # 의존성 패키지 목록
`-- web 
    |-- Dockerfile           # nginx 빌드
    |-- default.conf         # proxypass 설정파일
    `-- index.html           # 웹 정적파일

4 directories, 11 files
```

## 1. Docker build
```
docker build -t was:local ./was
docker build -t web:local ./web

docker tag was:local rainhyeon/three-tier-was:v1
docker tag web:local rainhyeon/three-tier-web:v3
```

## 2. Docker Push
```
docker push rainhyeon/three-tier-was:v1
docker push rainhyeon/three-tier-web:v3
```

## 3. 베포
```
kubectl apply -f k8s/
```

- 배포 결과
```
controlplane:~$ k get all -n three-tier -o wide
NAME                       READY   STATUS    RESTARTS   AGE     IP             NODE     NOMINATED NODE   READINESS GATES
pod/db-79d697f7fb-d2mnm    1/1     Running   0          6m27s   192.168.1.5    node01   <none>           <none>
pod/was-5b4f7fb55b-lsmbj   1/1     Running   0          20s     192.168.1.10   node01   <none>           <none>
pod/was-5b4f7fb55b-rh9xx   1/1     Running   0          62s     192.168.1.9    node01   <none>           <none>
pod/web-5bc4d547cd-mk57v   1/1     Running   0          6m26s   192.168.1.6    node01   <none>           <none>

NAME          TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)        AGE     SELECTOR
service/db    ClusterIP   10.104.248.97    <none>        5432/TCP       6m27s   app=db
service/was   ClusterIP   10.96.203.23     <none>        80/TCP         6m26s   app=was
service/web   NodePort    10.109.198.143   <none>        80:32226/TCP   6m26s   app=web

NAME                  READY   UP-TO-DATE   AVAILABLE   AGE     CONTAINERS   IMAGES                        SELECTOR
deployment.apps/db    1/1     1            1           6m27s   postgres     postgres:16                   app=db
deployment.apps/was   2/2     2            2           6m27s   was          rainhyeon/three-tier-was:v1   app=was
deployment.apps/web   1/1     1            1           6m26s   web          rainhyeon/three-tier-web:v1   app=web

NAME                             DESIRED   CURRENT   READY   AGE     CONTAINERS   IMAGES                        SELECTOR
replicaset.apps/db-79d697f7fb    1         1         1       6m27s   postgres     postgres:16                   app=db,pod-template-hash=79d697f7fb
replicaset.apps/was-5b4f7fb55b   2         2         2       6m27s   was          rainhyeon/three-tier-was:v1   app=was,pod-template-hash=5b4f7fb55b
replicaset.apps/web-5bc4d547cd   1         1         1       6m26s   web          rainhyeon/three-tier-web:v1   app=web,pod-template-hash=5bc4d547cd
```


## 4. 통신 테스트
### 4-1. 임의의 파드 띄워서 web 호출
```
controlplane:~$ kubectl -n three-tier run curl --rm -it --image=curlimages/curl --restart=Never -- sh
All commands and output from this session will be recorded in container logs, including credentials and sensitive information passed through the command prompt.
If you don't see a command prompt, try pressing enter.
~ $ curl -sS http://web/
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>3-Tier Lab</title>
  </head>
  <body>
    <h1>3-Tier Lab (web -> was -> db)</h1>
    <button id="btn">Call /api/ping</button>
    <pre id="out"></pre>

    <script>
      const out = document.getElementById("out");
      document.getElementById("btn").onclick = async () => {
        out.textContent = "calling...";
        try {
          const r = await fetch("/api/ping");
          const t = await r.text();
          out.textContent = t;
        } catch (e) {
          out.textContent = String(e);
        }
      };
    </script>
  </body>
</html>
~ $ 
```
- web 통신이 잘되는것 확인 가능함

### 4-2. web -> was 통신 확인
```
~ $ curl -sS http://web/api/ping
<!doctype html>
<html lang=en>
<title>404 Not Found</title>
<h1>Not Found</h1>
<p>The requested URL was not found on the server. If you entered the URL manually please check your spelling and try again.</p>
```
🚨 통신 불가능
1. WAS + DB 정상인지 확인하기
```
~ $ curl -i http://was/api/ping
HTTP/1.1 200 OK
Server: gunicorn
Date: Thu, 26 Feb 2026 15:17:20 GMT
Connection: keep-alive
Content-Type: application/json
Content-Length: 61

{"db_time":"2026-02-26T15:17:20.479580+00:00","status":"ok"}
```
- 200 OK + db_time → WAS↔DB 통신 완전

2. WAS 엔드포인트 확인
```
controlplane:~/kubernetes-3Tier$ kubectl -n three-tier get endpoints was -o wide
Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
NAME   ENDPOINTS                             AGE
was    192.168.1.13:8080,192.168.1.14:8080   25m
```
- Pod IP 2개 잡힘 → Service/Endpoint 정상

2. Domain 확인
```
~ $ cat /etc/resolv.conf 
search three-tier.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.96.0.10
options ndots:5
```
- 현재 "was.three-tier.svc.cluster.local"는 10.96.0.10(Coredns의 ClusterIP)로 보내면된다
- Coredns의 ClusterIP 확인
```
controlplane:~/kubernetes-3Tier$ kubectl -n kube-system get svc | grep dns
kube-dns   ClusterIP   10.96.0.10   <none>        53/UDP,53/TCP,9153/TCP   25d
```

3. curl http://web/api/ping만 504가 나는 건
- web/default.conf 수정 필요

<수정전>
```
location /api/ {
  proxy_pass http://was.three-tier.svc.cluster.local/;
}
```
<수정후>
```
location /api/ {
  proxy_pass http://was.three-tier.svc.cluster.local;
}
```
📍 수정 이유
- Nginx URI 치환 규칙 문제로


## 5. 수정 후 통신 테스트
```
~ $ curl http://web/api/ping
{"db_time":"2026-02-26T15:48:49.604487+00:00","status":"ok"}
```
- DB와 잘 연결되는 것을 확인할 수 있다

## 6. iptable 확인
```
node01:~$ sudo iptables -t nat -L -n -v | grep -i three-tier
    0     0 KUBE-MARK-MASQ  0    --  *      *       0.0.0.0/0            0.0.0.0/0            /* masquerade traffic for three-tier/web external destinations */
    0     0 KUBE-EXT-KNWFBHKZ4E3RECU6  6    --  *      *       0.0.0.0/0            127.0.0.0/8          /* three-tier/web */ tcp dpt:30688 nfacct-name  localhost_nps_accepted_pkts
    0     0 KUBE-EXT-KNWFBHKZ4E3RECU6  6    --  *      *       0.0.0.0/0            0.0.0.0/0            /* three-tier/web */ tcp dpt:30688
    0     0 KUBE-MARK-MASQ  0    --  *      *       192.168.1.4          0.0.0.0/0            /* three-tier/db */
    1    60 DNAT       6    --  *      *       0.0.0.0/0            0.0.0.0/0            /* three-tier/db */ tcp to:192.168.1.4:5432
    0     0 KUBE-MARK-MASQ  0    --  *      *       192.168.1.7          0.0.0.0/0            /* three-tier/web */
    1    60 DNAT       6    --  *      *       0.0.0.0/0            0.0.0.0/0            /* three-tier/web */ tcp to:192.168.1.7:8080
    0     0 KUBE-MARK-MASQ  0    --  *      *       192.168.1.5          0.0.0.0/0            /* three-tier/was */
    1    60 DNAT       6    --  *      *       0.0.0.0/0            0.0.0.0/0            /* three-tier/was */ tcp to:192.168.1.5:8080
    0     0 KUBE-MARK-MASQ  0    --  *      *       192.168.1.6          0.0.0.0/0            /* three-tier/was */
    0     0 DNAT       6    --  *      *       0.0.0.0/0            0.0.0.0/0            /* three-tier/was */ tcp to:192.168.1.6:8080
    1    60 KUBE-SVC-HKZHEGDCHKYDZHT2  6    --  *      *       0.0.0.0/0            10.96.80.152         /* three-tier/db cluster IP */ tcp dpt:5432
    1    60 KUBE-SVC-OJARZYDBC2YBWB7N  6    --  *      *       0.0.0.0/0            10.102.18.214        /* three-tier/was cluster IP */ tcp dpt:80
    1    60 KUBE-SVC-KNWFBHKZ4E3RECU6  6    --  *      *       0.0.0.0/0            10.97.8.255          /* three-tier/web cluster IP */ tcp dpt:80
    0     0 KUBE-MARK-MASQ  6    --  *      *      !192.168.0.0/16       10.96.80.152         /* three-tier/db cluster IP */ tcp dpt:5432
    1    60 KUBE-SEP-LUX7EMOFFC77R3P4  0    --  *      *       0.0.0.0/0            0.0.0.0/0            /* three-tier/db -> 192.168.1.4:5432 */
    0     0 KUBE-MARK-MASQ  6    --  *      *      !192.168.0.0/16       10.97.8.255          /* three-tier/web cluster IP */ tcp dpt:80
    1    60 KUBE-SEP-NHAO6WC3G2JJERLX  0    --  *      *       0.0.0.0/0            0.0.0.0/0            /* three-tier/web -> 192.168.1.7:8080 */
    0     0 KUBE-MARK-MASQ  6    --  *      *      !192.168.0.0/16       10.102.18.214        /* three-tier/was cluster IP */ tcp dpt:80
    1    60 KUBE-SEP-NUSDDAKE6UKWRFTS  0    --  *      *       0.0.0.0/0            0.0.0.0/0            /* three-tier/was -> 192.168.1.5:8080 */ statistic mode random probability 0.50000000000
    0     0 KUBE-SEP-OUD6CWY7HGPBH4PB  0    --  *      *       0.0.0.0/0            0.0.0.0/0            /* three-tier/was -> 192.168.1.6:8080 */
```
📍 예시 의미
| pkts | bytes | target | prot | opt | in | out | source      | destination | 주석부분 |
|------|-------|--------|------|-----|----|-----|------------|-------------|----------|
| 1    | 60    | DNAT   | 6    | --  | *  | *   | 0.0.0.0/0  | 0.0.0.0/0   | /* three-tier/was */ tcp to:192.168.1.5:8080 |
- 1개 패킷이
- 60바이트 크기로
- TCP 프로토콜이며
- 어떤 인터페이스든 상관없이
- 목적지를
- 192.168.1.5:8080 으로 바꿨다

📍 항목 뜻
| 항목              | 의미            | 설명                                                               |
| --------------- | ------------- | ---------------------------------------------------------------- |
| **pkts**        | 패킷 수          | 해당 규칙을 통과한 패킷 개수. 규칙이 실제로 사용되고 있는지 판단하는 핵심 지표                    |
| **bytes**       | 바이트 수         | 해당 규칙을 통과한 총 데이터 크기                                              |
| **target**      | 실행 동작         | 규칙이 수행하는 동작. 예: `DNAT`, `SNAT`, `KUBE-SVC-XXXX`, `KUBE-SEP-XXXX` |
| **prot**        | 프로토콜          | `6=TCP`, `17=UDP`, `1=ICMP`                                      |
| **opt**         | 옵션            | 일반적으로 `--`, 특별한 옵션이 있을 경우 표시                                     |
| **in**          | 입력 인터페이스      | 패킷이 들어오는 네트워크 인터페이스 (`*` = 전체)                                   |
| **out**         | 출력 인터페이스      | 패킷이 나가는 네트워크 인터페이스 (`*` = 전체)                                    |
| **source**      | 출발지 IP        | 매칭되는 출발지 주소 범위                                                   |
| **destination** | 목적지 IP        | 매칭되는 목적지 주소 범위                                                   |
| **주석부분**        | kube-proxy 설명 | 어떤 Service/Namespace인지와 실제 DNAT 대상 Pod IP 표시                     |

# Kubernetes 3-Tier 네트워크 통신 흐름 분석  
### (Pod A → WEB → WAS → DB)

---

## 🧾 시나리오

Pod A에서 다음 명령을 실행한다.

```bash
curl http://web/api/ping
```

# 1️⃣ 전체 네트워크 흐름 개요

```
Pod A
  ↓
ClusterIP (web)
  ↓
WEB Pod
  ↓
ClusterIP (was)
  ↓
WAS Pod
  ↓
ClusterIP (db)
  ↓
DB Pod
```

✔ 각 Service 통신마다 **iptables NAT(DNAT)** 이 수행된다.

---

# 2️⃣ Pod A → WEB Service 통신 과정

## ① DNS 해석

```
web.three-tier.svc.cluster.local
→ 10.97.8.255 (ClusterIP)
```

---

## ② Pod → Node 브리지

```
Pod A
  ↓ (veth)
Node Bridge (cni0 / flannel.1)
```

Pod 네트워크는 veth를 통해 Node 브리지로 전달된다.

---

## ③ iptables NAT 처리 (PREROUTING)

```
nat 테이블
PREROUTING
  ↓
KUBE-SERVICES
```

매칭 조건:

```
destination = 10.97.8.255
```

점프:

```
→ KUBE-SVC-XXXX
```

---

## ④ Service → Endpoint 선택

```
KUBE-SVC-XXXX
  ↓
KUBE-SEP-XXXX
```

---

## ⑤ DNAT 수행

```
DNAT → 192.168.1.7:8080 (WEB Pod IP)
```

ClusterIP가 실제 Pod IP로 변경된다.

---

## ⑥ FORWARD 체인

```
filter 테이블
FORWARD
```

허용되면:

```
Node → veth → WEB Pod
```

---

# 3️⃣ WEB → WAS 통신 과정

WEB 컨테이너 내부:

```nginx
proxy_pass http://was;
```

DNS:

```
was → 10.102.18.214
```

동일한 iptables 흐름 반복:

```
PREROUTING (nat)
  ↓
KUBE-SERVICES
  ↓
KUBE-SVC-XXXX
  ↓
KUBE-SEP-XXXX
  ↓
DNAT → 192.168.1.5:8080 (WAS Pod)
  ↓
FORWARD
```

---

# 4️⃣ WAS → DB 통신 과정

WAS 내부:

```python
psycopg2.connect(host="db", port=5432)
```

DNS:

```
db → 10.96.80.152
```

iptables 흐름:

```
PREROUTING (nat)
  ↓
KUBE-SVC-XXXX
  ↓
KUBE-SEP-XXXX
  ↓
DNAT → 192.168.1.4:5432 (DB Pod)
  ↓
FORWARD
```

---

# 5️⃣ 응답 패킷 처리

DNAT이 수행되면 Linux 커널의 **conntrack** 이 세션을 기록한다.

응답 경로:

```
DB Pod 
  → WAS Pod 
  → WEB Pod 
  → Pod A
```

필요 시:

```
POSTROUTING (nat)
  ↓
MASQUERADE (SNAT)
```

---

# 6️⃣ iptables 체인 순서 요약

각 Service 통신마다 반복되는 체인 순서:

```
1. nat PREROUTING
2. KUBE-SERVICES
3. KUBE-SVC-XXXX
4. KUBE-SEP-XXXX
5. DNAT (ClusterIP → PodIP)
6. filter FORWARD
7. nat POSTROUTING (필요 시 SNAT)
```

---

# 7️⃣ 핵심 개념 정리

| 개념 | 설명 |
|------|------|
| ClusterIP | 가상 IP, 실제 Pod IP가 아님 |
| kube-proxy | iptables 규칙 생성 |
| KUBE-SVC | Service 체인 |
| KUBE-SEP | Endpoint 체인 |
| DNAT | 목적지 주소 변환 |
| FORWARD | 노드가 라우터 역할 수행 |
| conntrack | NAT 세션 상태 유지 |

---

# 📌 핵심 포인트 한 줄 요약

> Kubernetes Service 통신은 **ClusterIP → iptables DNAT → Pod IP 변환** 과정이며,  
> kube-proxy가 생성한 iptables 체인이 이를 제어한다.


# 장애 시나리오
```
Pod A
  ↓ (veth)
Node의 Linux Bridge (CNI)
  ↓
iptables (FORWARD 체인)
  ↓
라우팅 테이블
  ↓
Pod B
```

## 1. Worker 노드의 방화벽 활성화
```
sudo ufw status
sudo ufw enable
sudo ufw default deny routed
```

## 2. 시스템 환경 변수 설정
- 브리지 인터페이스를 통과하는 패킷을 iptables를 거치지 않도록한다
```
# 환경변수 설정
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
bridge-nf-call-iptables=0
EOF

# 반영

```
→ kube-proxy가 만든 NAT/DNAT 규칙이 적용되지 않음
→ Service 통신이 실패할 수 있음



