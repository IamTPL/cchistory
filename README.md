# claude-backup

CLI để backup và xem lịch sử Claude Code offline. Tool tự dò dữ liệu Claude Code, gom hội thoại theo project, rồi build Markdown và HTML viewer tĩnh để mở lại bằng trình duyệt.

## Tính năng

- Backup lịch sử Claude Code thành thư mục local.
- Xuất mỗi hội thoại ra `markdown/*.md` và `conversations/*.html`.
- Tạo `index.html` để duyệt, tìm kiếm và mở hội thoại theo project.
- Chạy offline bằng `file://`; có thêm lệnh `serve` khi dữ liệu rất lớn.
- Rebuild sạch phần output do tool sở hữu, không xóa file riêng của người dùng trong thư mục output.

## Cài đặt

### Ubuntu, WSL, macOS

Khuyến nghị dùng `pipx`:

```bash
pipx install .
```

Nếu shell chưa nhận lệnh `claude-backup`, kiểm tra PATH của `pipx`:

```bash
pipx ensurepath
```

### Windows

Dùng PowerShell hoặc CMD:

```powershell
python -m pip install .
```

Hoặc:

```powershell
pip install .
```

Nếu không gọi được `claude-backup`, thêm thư mục `Scripts` của Python vào PATH. Thường gặp ở:

```text
%APPDATA%\Python\Python3x\Scripts
```

hoặc thư mục `Scripts` bên trong virtual environment đang dùng.

## Cách chạy

Chạy mặc định: tự dò source, ghi ra `./claude_backup`, rồi mở viewer.

```bash
claude-backup
```

Build nhưng không tự mở trình duyệt:

```bash
claude-backup --no-open
```

Chỉ định thư mục source và output:

```bash
claude-backup --source <projects> -o <out>
```

Các tùy chọn thường dùng:

```bash
claude-backup --by-activity
claude-backup --no-tools
claude-backup --full-results
claude-backup --all-sources
claude-backup --incremental
claude-backup --no-subagents
```

- `--by-activity`: sắp theo lần hoạt động cuối thay vì thời điểm bắt đầu.
- `--no-tools`: ẩn chi tiết tool call trong nội dung export.
- `--full-results`: giữ đầy đủ tool result, không rút gọn preview.
- `--all-sources`: dùng tất cả source tự dò được thay vì chỉ source đầu tiên.
- `--incremental`: chỉ render lại hội thoại có thay đổi để chạy nhanh hơn.
- `--no-subagents`: bỏ qua session sub-agent nếu phiên bản hiện tại có hỗ trợ.

Xem toàn bộ cờ:

```bash
claude-backup -h
```

## Serve viewer

Viewer mặc định mở trực tiếp `index.html` bằng `file://`, tiện nhất cho backup nhỏ và vừa.

Khi dữ liệu rất lớn, chạy server local sẽ ổn định hơn:

```bash
claude-backup serve
```

Tùy chọn:

```bash
claude-backup serve -o <out>
claude-backup serve --output <out>
claude-backup serve --host 127.0.0.1 --port 8000
claude-backup serve --no-open
```

Trade-off:

- `file://`: nhanh, đơn giản, không cần server.
- `serve`: tốt hơn khi có rất nhiều conversation, tránh giới hạn của trình duyệt với file local và mở đường cho lazy-load ổn định hơn.

## Tự dò source

Nếu không truyền `--source`, tool tự tìm các thư mục `projects` của Claude Code theo thứ tự:

1. `CLAUDE_CONFIG_DIR/projects` nếu có biến môi trường `CLAUDE_CONFIG_DIR`.
2. `~/.claude/projects`.
3. Khi chạy trong WSL: quét thêm `/mnt/c/Users/*/.claude/projects`.
4. Khi chạy trên Windows: quét thêm WSL qua `\\wsl$` và `\\wsl.localhost`.

Nếu không tìm thấy source, truyền thủ công:

```bash
claude-backup --source <duong-dan-den-projects>
```

## Output

Mặc định output nằm trong `./claude_backup`:

```text
claude_backup/
  conversations/
  markdown/
  assets/
  index.html
```

Mỗi lần full rebuild, tool chỉ xóa và tạo lại các phần nó sở hữu:

- `conversations/`
- `markdown/`
- `assets/`
- `index.html`

Các file hoặc thư mục khác do người dùng đặt trong output sẽ được giữ nguyên.

## Development

Cài editable kèm dependency dev:

```bash
python -m pip install -e .[dev]
```

Chạy test:

```bash
pytest
```
