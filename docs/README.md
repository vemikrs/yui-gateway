# YuiGateway ドキュメント

このディレクトリには、YuiGatewayの包括的なドキュメントが含まれています。

## 📚 ドキュメント構成

### 🚀 利用ガイド

- **[LOCAL_USAGE.md](LOCAL_USAGE.md)** - 日本語版ローカル使用ガイド
  - 自動プロビジョニング手順
  - デプロイメント情報の確認方法
  - 新旧モデルのパラメータ対応
  - 詳細なトラブルシューティング

- **[LOCAL_USAGE_EN.md](LOCAL_USAGE_EN.md)** - 英語版ローカル使用ガイド
  - Complete setup instructions
  - API usage examples
  - Troubleshooting guide

### 🏗️ アーキテクチャ・設計

- **[overview.md](overview.md)** - システムアーキテクチャ概要
  - コアコンセプトと設計思想
  - 認証・API・プロキシ・設定の4層構成
  - 自動プロビジョニングシステム
  - セキュリティ設計とデータフロー

### 💡 実用例・ユースケース

- **[use-cases.md](use-cases.md)** - 具体的なユースケース集
  - 個人開発環境での利用
  - チーム開発・CI/CD統合
  - YuiHub思想記録プラットフォーム連携
  - エンタープライズ導入事例
  - 特殊用途・ハイブリッド環境

## 🔗 関連ドキュメント

### プロジェクトルート
- **[README.md](../README.md)** - プロジェクト概要とクイックスタート
- **[SETUP.md](../SETUP.md)** - 手動セットアップガイド
- **[TESTING.md](../TESTING.md)** - テスト実行ガイド

### 開発者向け
- **[gateway/README.dev.md](../gateway/README.dev.md)** - 開発ガイド
- **[tests/README.md](../tests/README.md)** - テストスイート詳細

## 🎯 読み始め方

### 初回利用者
1. **[LOCAL_USAGE.md](LOCAL_USAGE.md)** で基本的な使用方法を確認
2. 自動プロビジョニングで簡単セットアップ
3. **[use-cases.md](use-cases.md)** で自分の用途に近い例を参考

### アーキテクト・設計者
1. **[overview.md](overview.md)** でシステム全体像を把握
2. **[use-cases.md](use-cases.md)** で導入パターンを検討
3. セキュリティ要件との適合性を評価

### 開発者
1. **[gateway/README.dev.md](../gateway/README.dev.md)** で技術詳細を確認
2. **[TESTING.md](../TESTING.md)** でテスト環境をセットアップ
3. 拡張・カスタマイズの方向性を検討

## 📖 ドキュメント品質

- **自動検証**: 全コード例の動作確認済み
- **実装同期**: 最新機能と実装状況を反映
- **多言語対応**: 日本語・英語での詳細説明
- **段階的学習**: 基礎から応用まで体系的に構成

## 🤝 フィードバック

ドキュメントの改善提案や追加要望は、[GitHub Issues](https://github.com/vemikrs/yui-gateway/issues)でお知らせください。

---

**最終更新**: 2025-11-05
**カバレッジ**: 全機能の包括的ドキュメント完備
