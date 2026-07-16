# micam_dev

小米摄像头「截流」二次开发工程：不刷机、不破坏米家绑定，在局域网内把小米私有 P2P 视频流转换成标准 RTSP，供 FFmpeg / OpenCV / 任意 NVR 使用。

技术栈：只用 [`AlexxIT/go2rtc`](https://github.com/AlexxIT/go2rtc) 一个服务。go2rtc 内置了小米摄像头的 `xiaomi://` 源，登录一次小米账号后由它自己去云端换取该摄像头的短时 P2P 凭证，然后在局域网内直连摄像头拉流，对外暴露标准 RTSP/WebRTC/HLS 地址。

```
小米摄像头 ⇄(局域网 P2P)⇄ go2rtc ──▶ FFmpeg / OpenCV / NVR / HomeAssistant
                ▲
                └─(仅换凭证时)── 小米云端
```

> 之前的方案里额外套了 miloco + micam 两层桥接，本工程已经去掉了 —— 那套架构依赖 miloco 内置的 AI/视觉大模型子服务，即使你完全用不上 AI 功能，也会因为缺少本地模型服务而反复崩溃重启。go2rtc 原生支持小米摄像头之后，直接更简单更稳。参考：[go2rtc issue #1982 兼容列表](https://github.com/AlexxIT/go2rtc/issues/1982)、[miiot/micam 相关讨论](https://github.com/miiot/micam/discussions/29)。

## 一、前置条件

- Docker + Docker Compose v2（`docker compose version` 能跑通）
- 摄像头、跑 Docker 的主机、开发机三者在**同一个二层局域网/网段**（小米设备的 P2P 大多不支持跨网段，这是最常见的失败原因，见下方调试章节）
- 摄像头已在米家 App 中正常绑定、可正常查看直播
- 摄像头型号在 go2rtc 的 [兼容列表](https://github.com/AlexxIT/go2rtc/issues/1982) 里 —— 小米智能摄像机2 云台版（`chuangmi.camera.039c01`）已确认完全支持（`cs2+tcp`，`hevc`+`opus`）；具体型号可在米家 App 设备详情页"更多信息"里核对

## 二、快速部署

```bash
git clone <this repo> micam_dev   # 或直接在本仓库目录操作
cd micam_dev
cp .env.example .env
docker compose up -d
docker compose ps      # go2rtc 应为 running
docker compose logs -f # 出问题时先看这里
```

## 三、添加摄像头（在 go2rtc WebUI 里操作，不用改配置文件）

1. 浏览器打开 `http://<跑Docker的主机IP>:1984`。
2. 点击 **Add** → 选择 **Xiaomi**。
3. 输入小米账号用户名密码登录；如果触发风控会要求邮箱/短信验证码或图形验证码，按提示完成。
4. 登录成功后账号会被加入，页面上可以"加载账号下的摄像头"，选中你要用的这台，go2rtc 会自动生成对应的 stream。
5. 添加成功后，go2rtc 会把账号 token 写进 `go2rtc/go2rtc.yaml` 的 `xiaomi:` 段，把 stream 写进 `streams:` 段，类似：

```yaml
xiaomi:
  1234567890: V1:xxxxxxxx    # 账号 token，go2rtc 自动写入，不用手填

streams:
  cam0: "xiaomi://1234567890:cn@192.168.2.xx?did=987654321&model=chuangmi.camera.039c01"
```

如果 WebUI 向导对你的账号/网络环境走不通，也可以直接手动编辑 `go2rtc/go2rtc.yaml` 加上面这样一行 `streams`，`user_id`/`token` 从向导登录后自动生成的段里复制，`did`（设备 ID）和 `model` 型号是唯一需要你自己确认的两项。

**画质档位**：默认可能协商到低清子码流。在 URL 后加 `&subtype=hd`（或 `sd`，或数字 `0`-`5`）指定档位，比如：

```yaml
streams:
  cam0: "xiaomi://1234567890:cn@192.168.2.xx?did=987654321&model=chuangmi.camera.039c01&subtype=hd"
```

改完配置后重启使其生效：

```bash
docker compose restart go2rtc
```

## 四、验证 RTSP 流

- go2rtc 管理页面 `http://<主机IP>:1984` 的 Streams 列表里应该能看到 `cam0`，有画面缩略图即代表打通了。
- 命令行验证：

```bash
ffprobe rtsp://<主机IP>:8554/cam0
# 或者直接用 VLC / ffplay 打开同样的地址看画面
```

打不开就去看 `docker compose logs -f go2rtc`，常见报错见下方"调试"章节。

## 五、多摄像头

同一个账号下的其他摄像头，回到 WebUI 的 Xiaomi 添加向导里"加载摄像头"列表继续选,或者直接在 `go2rtc/go2rtc.yaml` 的 `streams:` 段里再加一行(换一下 `did`/`model`/流名),`docker compose restart go2rtc` 生效。不需要额外容器。

## 六、二次开发示例

拿到标准 RTSP 地址之后，怎么用完全和摄像头品牌无关了 —— OpenCV 的 `cv2.VideoCapture` 能直接打开它。

**OpenCV 读帧（主要用法）：**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r scripts/requirements.txt
python scripts/capture_frame.py --stream cam0
```

`scripts/capture_frame.py` 只做了最基础的事：连上 `rtsp://127.0.0.1:8554/cam0`，循环 `cap.read()` 拿到 `frame`（BGR numpy 数组）和毫秒级时间戳，自己的检测/识别逻辑写进 `process_frame()` 里就行。默认会弹一个窗口实时显示画面（按 `q` 退出）；如果是在没有图形界面的服务器上跑，加 `--no-display`。核心代码只有几行：

```python
cap = cv2.VideoCapture("rtsp://127.0.0.1:8554/cam0", cv2.CAP_FFMPEG)
while True:
    ok, frame = cap.read()
    if not ok:
        continue
    # frame 就是这一帧，直接喂给你自己的模型/逻辑
```

**如果还需要落盘存证据（可选，非必需）：**

```bash
./scripts/record_segments.sh cam0 ./recordings/cam0 600   # 每 600 秒一段，stream copy 不转码
```

**截图单帧（用 go2rtc 自带的 HTTP 接口，不用装额外工具）：**

```bash
curl "http://127.0.0.1:1984/api/frame.jpeg?src=cam0" -o snapshot.jpg
```

## 七、调试 / 常见问题

| 现象 | 排查方向 |
|---|---|
| WebUI 里加了账号，但摄像头列表是空的/加载失败 | 摄像头和跑 Docker 的主机必须在同一网段，小米大部分 IoT 设备的 P2P 不支持跨子网；先在米家 App 里确认摄像头本身在线 |
| stream 有画面但一直黑屏/连不上 | 看 `docker compose logs -f go2rtc`；确认 `go2rtc.yaml` 里 `did`/`model` 没抄错 |
| 花屏、卡顿、偶尔断流 | 尝试在 stream URL 后加 `&subtype=sd` 换成低清流测试是否网络带宽问题；也可能是该型号已知的兼容性限制，去 [go2rtc issue #1982](https://github.com/AlexxIT/go2rtc/issues/1982) 看有没有已知问题 |
| 镜像拉不下来 / 超时 | `ghcr.nju.edu.cn` 是国内镜像，若不可达把 `docker-compose.yml` 里的 `image:` 换成注释掉的 `ghcr.io/...` 那一行 |
| 改了 `go2rtc.yaml` 不生效 | `docker compose restart go2rtc` 让配置重新加载 |

## 八、已知限制

- 并非所有小米摄像头型号都支持，以 [go2rtc issue #1982](https://github.com/AlexxIT/go2rtc/issues/1982) 的兼容列表为准。
- 每次连接摄像头都需要一次访问小米云端换取 P2P 密钥；之后的取流是纯局域网 P2P。
- 摄像头与 Docker 主机跨网段基本不可用。

## 参考

- <https://github.com/AlexxIT/go2rtc>
- <https://github.com/AlexxIT/go2rtc/blob/master/internal/xiaomi/README.md>
- <https://github.com/AlexxIT/go2rtc/issues/1982>（型号兼容列表）
