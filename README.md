# micam_dev

小米摄像头「截流」二次开发工程：不刷机、不破坏米家绑定，在局域网内把小米私有 P2P 视频流转换成标准 RTSP，供 FFmpeg / OpenCV / 任意 NVR 使用。

技术栈基于两个开源项目：

- [`XiaoMi/xiaomi-miloco`](https://github.com/XiaoMi/xiaomi-miloco)（社区镜像 `miiot/miloco`）：向小米云端换取该摄像头的短时 P2P 凭证，之后在局域网内直连摄像头拉流，只有换凭证这一步需要外网。
- [`miiot/micam`](https://github.com/miiot/micam)：桥接服务，每路摄像头一个实例，把 miloco 吐出的裸流转推进 go2rtc。
- [`AlexxIT/go2rtc`](https://github.com/AlexxIT/go2rtc)：标准 RTSP/WebRTC/HLS 服务器，对外暴露 `rtsp://.../cam0` 这样的标准地址。

```
小米摄像头 ⇄(局域网 P2P)⇄ miloco ──(裸流)──▶ micam ──(RTSP 推流)──▶ go2rtc ──▶ FFmpeg / OpenCV / NVR / HomeAssistant
                 ▲
                 └─(仅换凭证时)── 小米云端
```

## 一、前置条件

- Docker + Docker Compose v2（`docker compose version` 能跑通）
- 摄像头、跑 Docker 的主机、开发机三者在**同一个二层局域网/网段**（小米设备的 P2P 大多不支持跨网段，这是最常见的失败原因，见下方调试章节）
- 摄像头已在米家 App 中正常绑定、可正常查看直播
- 一个用于开发调试的、独立于日常使用的米家账号更安全（可选，但推荐）

## 二、快速部署

```bash
git clone <this repo> micam_dev   # 或直接在本仓库目录操作
cd micam_dev
cp .env.example .env
```

编辑 `.env`，先填两项，其余先留空：

```env
MILOCO_PASSWORD=   # 下一步生成
CAMERA_ID=         # 稍后从 Miloco 网页里找
```

生成 `MILOCO_PASSWORD`（自己随便定一个明文密码，工具会转成 md5 小写）：

```bash
./scripts/gen_password.sh "your-chosen-password"
# 把输出的哈希值填进 .env 的 MILOCO_PASSWORD
```

启动：

```bash
docker compose up -d
docker compose ps      # 三个容器都应为 running/healthy
docker compose logs -f # 出问题时先看这里
```

## 三、首次配置 Miloco，绑定账号，拿到 CAMERA_ID

1. 浏览器打开 `https://<跑Docker的主机IP>:8000`（自签证书，浏览器会警告，选择"继续访问"）。
2. 首次进入会要求设置密码 —— 输入你刚才生成哈希时用的**明文密码**（不是哈希值）。
3. 登录后按提示"绑定小米账号"，选择账号所在地区，登录后会自动拉取米家下的设备列表。
4. 找摄像头的 `CAMERA_ID`（即设备 DID）：在 Miloco 网页里打开浏览器开发者工具（F12）→ Network 面板，点击/刷新对应摄像头卡片，观察请求里携带的 `did` 字段，把它填进 `.env` 的 `CAMERA_ID`。
5. 确认该摄像头在 Miloco 页面里显示为在线状态，再进行下一步——如果这里就显示离线，先解决这个问题，RTSP 侧不会有更多线索。

改完 `.env` 后重启 micam 让配置生效：

```bash
docker compose up -d
```

## 四、验证 RTSP 流

- go2rtc 的管理页面：`http://<主机IP>:1984`，Streams 里应该能看到 `cam0`（对应 `.env` 里 `RTSP_URL` 的路径名），有画面缩略图即代表打通了。
- 命令行验证：

```bash
ffprobe rtsp://<主机IP>:8554/cam0
# 或者直接用 VLC / ffplay 打开同样的地址看画面
```

打不开就去看 `docker compose logs -f micam1`，常见报错见下方"调试"章节。

## 五、多摄像头

复制 `docker-compose.yml` 里的 `micam2` 块（改名 `micam3` ...），并在 `.env` 补上对应的 `CAMERA_3_ID` / `CAMERA_3_RTSP_URL`，把 `scale: 0` 改成 `scale: 1`，再 `docker compose up -d`。

## 六、二次开发示例

拿到标准 RTSP 地址之后，怎么用完全和摄像头品牌无关了。

**FFmpeg 按时间分段录制（MP4）：**

```bash
./scripts/record_segments.sh cam0 ./recordings/cam0 600   # 每 600 秒一段，stream copy 不转码
```

**OpenCV 读帧做简单移动侦测（可在此基础上接自己的 AI 模型）：**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r scripts/requirements.txt
python scripts/capture_frame.py --stream cam0
```

**截图单帧（用 go2rtc 自带的 HTTP 接口，不用装额外工具）：**

```bash
curl "http://127.0.0.1:1984/api/frame.jpeg?src=cam0" -o snapshot.jpg
```

## 七、调试 / 常见问题

| 现象 | 排查方向 |
|---|---|
| Miloco 网页里摄像头就显示离线 | 摄像头和跑 Docker 的主机必须在同一网段，小米大部分 IoT 设备的 P2P 不支持跨子网；先确认两者 IP 前缀一致 |
| `docker compose logs miloco` 报证书/网络错误 | 换凭证这一步需要能访问小米云端，检查主机出网是否正常、DNS 是否正常 |
| go2rtc 里看不到对应的 stream / 有 stream 但一直黑屏 | 看 `docker compose logs micam1`，确认 `.env` 里 `CAMERA_ID`、`RTSP_URL` 没填错；`VIDEO_CODEC` 试试从 `hevc` 换成 `h264`（不同型号输出编码不同） |
| 镜像拉不下来 / 超时 | `ghcr.nju.edu.cn` 是国内镜像，若不可达把 `docker-compose.yml` 里三个 `image:` 换成注释掉的 `ghcr.io/...` 那一行 |
| 改了 `.env` 不生效 | 修改环境变量后必须 `docker compose up -d` 重建容器，`restart` 不够 |
| 想确认密码哈希对不对 | `./scripts/gen_password.sh "同一个明文密码"`，结果应与 `.env` 里 `MILOCO_PASSWORD` 完全一致（小写） |

## 八、已知限制

- 这套方案依赖社区对小米私有协议的逆向（miloco/micam），小米若更改协议，可能出现短暂失效，需等上游更新镜像。
- 换凭证阶段需要一次外网访问；之后的取流是纯局域网 P2P。
- 摄像头与 Docker 主机跨网段基本不可用。

## 参考

- <https://github.com/XiaoMi/xiaomi-miloco>
- <https://github.com/miiot/micam>
- <https://github.com/AlexxIT/go2rtc>
