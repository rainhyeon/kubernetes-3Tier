# kuberenete-3Tier
쿠버네티스에 배포할 3Tier 구축


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




