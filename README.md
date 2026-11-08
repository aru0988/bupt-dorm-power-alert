# 宿舍电量预警（北邮公寓缴费）

一个非官方的小工具：定时查询北邮「公寓缴费」里已绑定电表的剩余电量，低于阈值时通过 Server酱 推送到普通微信。

> 仅用于查询本人宿舍，不提供充值功能。本项目与北京邮电大学官方无关。

## 功能

- 每天 11:00、18:00 各查询一次
- 剩余电量 ≤ 阈值（默认 10 度）时推送微信
- 同一自然日最多提醒 1 次，充值回升后自动复位
- 推送内容包含：房间、剩余度数、约合金额、近 7 天日均、预计可用天数、抄表时间
- 推送文案可自定义（`message_template.txt`）
- 会话过期时会推送提醒，运行 `refresh_cookie.bat` 自动刷新
- 连续 3 次查询失败会推送异常提醒

## 效果示例

```text
⚠️ 宿舍电量预警
房间：x-x-xxx（xx校区 xx号楼 x层）
剩余：8.4 度（约 4.03 元，单价 0.48 元/度）
近 7 天日均：4.34 度/天
预计可用：约 1.9 天
抄表时间：2026-11-08 23:12
请及时充值
```

## 前置条件

- 北邮宿舍，且在「公寓缴费」中已绑定电表
- Windows 10/11，Python 3.10
- 电脑版微信已登录
- Server酱账号（微信扫码即可，免费 5 条/天）

## 快速开始

### 1. 下载代码并安装依赖

```powershell
cd <项目目录>
py -3.10 -m pip install -r requirements.txt
```

### 2. 配置 Server酱

1. 打开 <https://sct.ftqq.com>
2. 微信扫码登录
3. 关注「Server酱」公众号
4. 在 SendKey 页面复制 `SCT` 开头的密钥

### 3. 创建本地配置

```powershell
Copy-Item config.example.ini config.ini
Copy-Item message_template.example.txt message_template.txt
```

编辑 `config.ini`：

- `[meter] meter_no`：公寓缴费 → 绑定信息 页面里的表计编号
- `[meter] room`：房间号（仅用于展示，可留示例）
- `[alert] threshold_kwh`：阈值，默认 10
- `[push] serverchan_sendkey`：第 2 步复制的 SendKey

### 4. 获取会话 Cookie

1. 在电脑版微信里打开「公寓缴费」（可从聊天/收藏/工作台进入）
2. 确认能看到自己的房间和剩余电量
3. 双击 `refresh_cookie.bat`，UAC 点「是」
4. 看到「会话已刷新」即可

> 脚本会用管理员权限做一次卷影复制，只读取微信 Cookie 库里的 xsgyfk 会话，临时副本用后即删。

### 5. 测试

```powershell
py -3.10 dorm_alert.py --test-push
py -3.10 dorm_alert.py --dry-run
```

- `--test-push`：微信收到测试消息
- `--dry-run`：打印当前电量、日均、预计天数，不推送

模拟预警：

```powershell
py -3.10 dorm_alert.py --dry-run --threshold 200
```

### 6. 安装定时任务

```powershell
powershell -ExecutionPolicy Bypass -File .\install_task.ps1
```

删除任务：

```powershell
powershell -ExecutionPolicy Bypass -File .\install_task.ps1 -Unregister
```

## 自定义推送文案

编辑 `message_template.txt`，支持以下占位符：

| 占位符 | 含义 |
| --- | --- |
| `{room}` | 房间号 |
| `{campus}` / `{building}` / `{floor}` | 校区 / 楼栋 / 楼层 |
| `{balance}` | 剩余度数（1 位小数） |
| `{price}` | 单价（2 位小数） |
| `{money}` | 约合金额（2 位小数） |
| `{avg_usage}` | 近 7 天日均（2 位小数） |
| `{days_left}` | 预计可用天数（1 位小数） |
| `{reading_time}` | 抄表时间 |

取值不可用时显示 `-`。未知占位符会退回默认模板并记录日志。

## 会话过期

脚本推送「登录已过期」时：

1. 在电脑版微信打开一次「公寓缴费」
2. 双击 `refresh_cookie.bat`
3. 再运行一次 `py -3.10 dorm_alert.py --dry-run` 确认

## 常见问题

**Q: 微信没收到测试消息？**
A: 确认已关注「Server酱」公众号；在 <https://sct.ftqq.com> 的 SendKey 页面重新复制密钥，注意不要手动抄写。

**Q: `refresh_cookie.bat` 提示卷影复制失败？**
A: 必须点 UAC 的「是」以管理员身份运行；确认电脑版微信正在运行。

**Q: `refresh_cookie.bat` 提示没有 xsgyfk 会话？**
A: 先在电脑版微信打开一次「公寓缴费」页面，再运行脚本。

**Q: 401 / 登录已过期？**
A: 按「会话过期」一节刷新 Cookie。

**Q: 任务计划没触发？**
A: 任务只在当前用户登录时运行；检查 `taskschd.msc` 中的 `DormPowerAlert`，或在项目目录手动运行 `py -3.10 dorm_alert.py --dry-run` 看日志 `logs/alert.log`。

**Q: 电量数据多久更新？**
A: 系统约每 2 小时更新一次，预警可能滞后约 2 小时。

## 文件说明

- `dorm_alert.py`：主程序
- `refresh_cookie.py` / `refresh_cookie.bat`：刷新会话
- `install_task.ps1`：任务计划
- `config.ini`：本地配置（不提交）
- `message_template.txt`：本地文案（不提交）
- `state.json`：运行状态（自动生成）
- `logs/alert.log`：日志

## 隐私与免责声明

- 本工具只查询本人宿舍的电量，不收集、不上传任何数据。
- `config.ini` 含会话 Cookie 和 Server酱 密钥，请勿分享或提交到公开仓库。
- 接口由学校系统提供，可能随学校更新而变化；本项目不保证长期可用。
- 不提供充值、缴费等任何资金操作。
- 使用本工具产生的后果由使用者自行承担。

## License

MIT
