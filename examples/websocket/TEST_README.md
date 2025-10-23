# WebSocket Connection Test Guide

この文書は、WebSocket接続の問題を診断するためのテストプログラムの使い方を説明します。

## テストプログラム

### 1. test_server.py
- **目的**: シンプルなWebSocketサーバー（デバッグ用）
- **特徴**: 詳細なログ出力、エラーハンドリング

### 2. test_client.py
- **目的**: main.pyと同じ接続パターンを使うテストクライアント
- **特徴**: main.pyと完全に同一のWebSocket接続コード

### 3. test_simple.py
- **目的**: 最もシンプルな接続テスト
- **特徴**: 同期的な単発テスト、問題の切り分けに最適

## 使い方

### ステップ1: 基本的な接続テスト

```bash
# ターミナル1: テストサーバーを起動
python test_server.py

# ターミナル2: シンプルテストを実行
python test_simple.py
```

成功時の出力:
```
✓ Connected successfully!
✓ Message sent: Hello from simple test
✓ Response received: welcome
✓ WebSocket connection test SUCCESSFUL
```

### ステップ2: main.pyと同じ接続パターンのテスト

```bash
# ターミナル1: テストサーバーを起動（既に起動している場合はスキップ）
python test_server.py

# ターミナル2: フル機能のテストクライアントを実行
python test_client.py
```

### ステップ3: 本番環境のテスト

```bash
# ターミナル1: 本番サーバーを起動
python server.py

# ターミナル2: テストクライアントで接続確認
python test_simple.py
```

## よくある問題と解決方法

### 1. ConnectionRefusedError

**エラーメッセージ**:
```
❌ ERROR: Connection refused
[WinError 1225] リモート コンピューターにより ネットワーク接続が拒否されました
```

**原因と解決方法**:
- サーバーが起動していない → `python test_server.py` または `python server.py` を先に実行
- ポートが間違っている → デフォルトは 8765
- ファイアウォールがブロックしている → ポート 8765 を許可

### 2. Address already in use

**エラーメッセージ**:
```
Port 8765 is already in use. Try a different port.
```

**解決方法**:
```bash
# 別のポートを使用
python test_server.py --port 9000
python test_simple.py ws://localhost:9000
```

### 3. Cannot assign requested address

**エラーメッセージ**:
```
❌ ERROR: Cannot assign requested address
```

**解決方法**:
- localhost または 127.0.0.1 を使用
- ホスト名が正しいか確認

## デバッグのヒント

### 1. 詳細なログを見る

test_server.py と test_client.py は DEBUG レベルのログを出力します：
- 接続の各ステップ
- 送受信メッセージの内容
- エラーの詳細

### 2. ネットワークの確認

```bash
# Windowsの場合
netstat -an | findstr 8765

# Linux/Macの場合
netstat -an | grep 8765
```

### 3. 段階的なテスト

1. まず `test_simple.py` で基本接続を確認
2. 次に `test_client.py` でmain.pyと同じパターンをテスト
3. 最後に本番の `server.py` + `main.py` + `client.py` を実行

## 接続フロー

```
1. Client → Server: TCP接続確立
2. Client → Server: WebSocketハンドシェイク
3. Server → Client: Welcome メッセージ
4. Client → Server: Register メッセージ (consumer として登録)
5. Server → Client: Registered 確認
6. Client ↔ Server: データの送受信
7. Client → Server: Ping (キープアライブ)
8. Server → Client: Pong (応答)
```

## トラブルシューティングチェックリスト

- [ ] サーバーが起動している
- [ ] ポート番号が一致している（デフォルト: 8765）
- [ ] ホスト名/IPアドレスが正しい
- [ ] ファイアウォールが通信を許可している
- [ ] 既に同じポートを使用しているプロセスがない
- [ ] WebSocketライブラリがインストールされている (`pip install websockets`)

## 成功の確認

test_simple.py が以下を表示すれば、WebSocket通信は正常です：
```
✓ WebSocket connection test SUCCESSFUL
```

この場合、main.py と client.py も正常に動作するはずです。