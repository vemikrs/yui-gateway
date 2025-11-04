# YuiGateway セットアップ手順

## 前提条件

- Python 3.10 以上
- Poetry（Python パッケージマネージャー）
- Azure OpenAI リソースへのアクセス
- Entra ID アプリ登録（クライアントクレデンシャル）

## セットアップ

### 1. 依存関係のインストール

```bash
# Poetry を使用する場合
poetry install

# または pip を使用する場合
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env.template` を `.env` にコピーして編集します：

```bash
cp .env.template .env
```

`.env` ファイルに以下の情報を入力：

```env
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
SCOPE=https://cognitiveservices.azure.com/.default
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
```

### 3. アプリケーションの起動

```bash
# スクリプトを使用
bash scripts/start_local.sh

# または直接起動
uvicorn gateway.routes:app --reload --host 0.0.0.0 --port 8000
```

## 使用方法

### ヘルスチェック

```bash
curl http://localhost:8000/health
```

### チャット補完リクエスト

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

### OpenAI ライブラリから使用

```python
import openai

# YuiGateway をベース URL として設定
openai.api_base = "http://localhost:8000/v1"
openai.api_key = "dummy"  # 認証は Entra ID で行われるため任意の値

response = openai.ChatCompletion.create(
    model="gpt-4",  # Azure OpenAI のデプロイメント名
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)

print(response.choices[0].message.content)
```

## トラブルシューティング

### トークン取得エラー

- `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET` が正しいか確認
- Azure Portal でアプリ登録の権限設定を確認
- `SCOPE` が正しいか確認（通常は `https://cognitiveservices.azure.com/.default`）

### Azure OpenAI 接続エラー

- `AZURE_OPENAI_ENDPOINT` が正しいか確認
- Azure OpenAI リソースでデプロイメントが作成されているか確認
- リクエストの `model` フィールドがデプロイメント名と一致しているか確認

## 開発

### テストの実行

```bash
pytest tests/
```

### コードフォーマット

```bash
black gateway/
```

## 次のステップ

- ログ記録機能の追加
- ストリーミングレスポンスのサポート
- 複数モデルのルーティング機能
- メトリクス収集（Prometheus/OpenTelemetry）
