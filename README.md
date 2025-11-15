# YuiGateway

Secure Entra ID-based proxy for Azure OpenAI.

---

## ⚡ Quick Start

```bash
# 1. Install
git clone https://github.com/vemikrs/yui-gateway.git
cd yui-gateway
poetry install

# 2. Setup Azure
python scripts/provision_env.py --login interactive --select

# 3. Start
bash scripts/start_local.sh

# 4. Test
curl http://localhost:8000/health
```

詳細: **[docs/QUICK_START.md](docs/QUICK_START.md)**

---

## 📚 Documentation

- **[クイックスタート](docs/QUICK_START.md)** - 5分で起動
- **[応用ガイド](docs/ADVANCED_USAGE.md)** - 詳細設定・カスタマイズ
- **[外部設定ファイル](docs/EXTERNAL_CONFIG.md)** - YAML設定
- **[アーキテクチャ](docs/overview.md)** - システム設計
- **[ユースケース](docs/use-cases.md)** - 利用例
- **[開発ガイド](gateway/README.dev.md)** - カスタマイズ
- **[テストガイド](TESTING.md)** - テスト実行

完全なドキュメント: **[docs/README.md](docs/README.md)**

---

## ✨ Features

- 🔐 **Secure** - Entra ID認証（APIキー不要）
- 🔌 **互換性** - OpenAI API互換
- 🚀 **自動設定** - ワンクリックでAzureセットアップ
- 🔄 **トークン管理** - 自動リフレッシュ
- ⚙️ **YAML設定** - 外部設定ファイル対応

---

## 🧪 Testing

```bash
pytest
pytest --cov=gateway --cov-report=html
```

---

## 🔗 Links

- [GitHub Issues](https://github.com/vemikrs/yui-gateway/issues)
- [YuiHub Project](https://github.com/vemikrs/yuihub)
