# YuiGateway クイックスタートガイド

**最速で動かす**: 初めての方向けの簡潔な手順です。

## 前提条件

- Python 3.10以上がインストールされている
- Azureアカウントを持っている
- Azure OpenAIリソースが作成済み（モデルがデプロイされている）

## 3ステップでセットアップ

### 1. インストール

```bash
git clone https://github.com/vemikrs/yui-gateway.git
cd yui-gateway
poetry install
```

または pip の場合:

```bash
pip install -e .
```

### 2. Azure自動設定

```bash
python scripts/provision_env.py --login interactive --select
```

これで以下が自動実行されます:
- Azureへのログイン
- サブスクリプション/リソースグループ/OpenAIリソースの選択
- アプリ登録の作成
- 認証情報の設定
- `.env`ファイルの生成

### 3. 起動

```bash
bash scripts/start_local.sh
```

## 動作確認

```bash
# ヘルスチェック
curl http://localhost:8000/health

# チャット補完を試す
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5-mini",
    "messages": [{"role": "user", "content": "こんにちは"}],
    "max_completion_tokens": 50
  }'
```

## Python から使う

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"  # 任意の値でOK
)

response = client.chat.completions.create(
    model="gpt-5-mini",
    messages=[{"role": "user", "content": "Pythonについて教えて"}],
    max_completion_tokens=100
)

print(response.choices[0].message.content)
```

## よくある問題

### エラー: `TENANT_ID が設定されていない`
→ 自動設定をもう一度実行: `python scripts/provision_env.py --login interactive --select`

### エラー: `モデルが見つからない`
→ 利用可能なモデルを確認: `python scripts/list_deployments.py`

### エラー: `ポート8000が使用中`
→ 別のポートを使う: `uvicorn gateway.routes:app --port 8001`

## 次のステップ

- **詳細な設定**: [ADVANCED_USAGE.md](ADVANCED_USAGE.md)
- **カスタマイズ**: [../gateway/README.dev.md](../gateway/README.dev.md)
- **外部設定ファイル**: [EXTERNAL_CONFIG.md](EXTERNAL_CONFIG.md)
- **アーキテクチャ**: [overview.md](overview.md)

---

**所要時間**: 約5分で起動完了
