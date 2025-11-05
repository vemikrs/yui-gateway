# YuiGateway ユースケース集

## 1. 個人開発環境

### ケース 1-1: ローカル開発環境でのAI統合

**状況**: PythonスクリプトやJupyter NotebookでAzure OpenAIを使いたい

**解決**:
```python
from openai import OpenAI

# YuiGateway経由で安全にAzure OpenAIへアクセス
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"
)

response = client.chat.completions.create(
    model="gpt-5-mini",
    messages=[{"role": "user", "content": "コードレビューして"}],
    max_completion_tokens=500
)
```

**メリット**:
- APIキー不要、Entra ID認証で安全
- 既存のOpenAIコードをそのまま使用可能
- 一度のセットアップで継続利用

### ケース 1-2: VS Codeでの統合開発

**状況**: VS Codeの拡張機能やGitHub Copilotと連携したい

**解決**: 組み込みVS Codeタスクでワンクリック操作
- `Ctrl+Shift+P` → "Tasks: Run Task" → "Start YuiGateway Server"
- 自動プロビジョニングで初回セットアップ完了
- デバッグコンソールでリアルタイム監視

**メリット**:
- IDEと統合されたワークフロー
- デバッグとテストの簡素化
- チーム間での設定共有

## 2. チーム開発

### ケース 2-1: 社内チャットボット連携

**状況**: SlackボットやTeamsボットでAzure OpenAIを利用したい

**解決**: YuiGatewayを社内サーバーにデプロイ
```bash
# 社内サーバーで起動
docker run -d -p 8000:8000 \
  -e TENANT_ID="your-tenant" \
  -e CLIENT_ID="your-client" \
  -e CLIENT_SECRET="your-secret" \
  -e AZURE_OPENAI_ENDPOINT="https://company-ai.openai.azure.com" \
  yui-gateway
```

**メリット**:
- Entra IDでユーザーアクセス制御
- APIキーの中央管理不要
- コスト・使用量の統合管理

### ケース 2-2: CI/CDパイプライン統合

**状況**: GitHub ActionsやAzure DevOpsでコードレビューやドキュメント生成を自動化

**解決**: シークレット管理でYuiGatewayをCI環境に統合
```yaml
# .github/workflows/ai-review.yml
- name: Setup YuiGateway
  run: |
    docker run -d -p 8000:8000 \
      -e TENANT_ID="${{ secrets.TENANT_ID }}" \
      -e CLIENT_ID="${{ secrets.CLIENT_ID }}" \
      -e CLIENT_SECRET="${{ secrets.CLIENT_SECRET }}" \
      yui-gateway

- name: AI Code Review
  run: |
    python scripts/ai_review.py --gateway-url http://localhost:8000
```

## 3. YuiHub連携

### ケース 3-1: SignalモードからのTrigger実行

**状況**: [YuiHub](https://github.com/vemikrs/yuihub)の思想記録プラットフォームからAI推論をトリガーしたい

**解決**: YuiHubのSignalモードからYuiGatewayを呼び出し
```python
# YuiHub Signalからの呼び出し例
class ThoughtAnalysisTrigger:
    def __init__(self):
        self.gateway_client = OpenAI(
            base_url="http://yui-gateway:8000/v1",
            api_key="dummy"
        )

    def analyze_thought_pattern(self, thought_record):
        response = self.gateway_client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "思想パターンを分析してください"},
                {"role": "user", "content": thought_record.content}
            ],
            max_completion_tokens=300
        )
        return response.choices[0].message.content
```

**メリット**:
- 思想と実行の適切な分離
- 推論過程の記録と分析
- Knot(意思決定ポイント)の追跡

### ケース 3-2: A5M2(思想記録ツール)連携

**状況**: A5M2での日常思考記録にAIアシスタントを統合

**解決**: A5M2のプラグインでYuiGatewayを利用
- メモ書き中にリアルタイムでAIサジェスト
- 過去の記録と関連付けて新しい気づきを提供
- 思考パターンの分析とフィードバック

## 4. エンタープライズ導入

### ケース 4-1: フォーチュン500企業でのAIガバナンス

**状況**: 大企業でのAI利用ポリシー・コンプライアンス管理

**解決**:
- **統合認証**: 企業のEntra IDでシングルサインオン
- **アクセス制御**: 部署・役職別のAI利用権限設定
- **監査ログ**: 全リクエストの記録とコンプライアンスチェック
- **コスト管理**: 部署別AI利用コストの可視化

### ケース 4-2: 金融機関での高セキュリティ環境

**状況**: 金融サービスでの厳格なコンプライアンス要求

**解決**:
- **オンプレミスデプロイ**: 完全に社内ネットワーク内で運用
- **データガバナンス**: 顧客データの外部送信防止
- **監査記録**: 全アクセスの詳細ログとユーザー特定
- **ゼロトラストアーキテクチャ**: 毎リクエストの認証・許可検証

## 5. 特殊用途

### ケース 5-1: マルチテナント環境

**状況**: コンサルタントやSaaS企業で複数顧客のAI環境管理

**解決**: テナント別のYuiGatewayインスタンス
```yaml
# docker-compose.yml
services:
  gateway-client-a:
    image: yui-gateway
    environment:
      TENANT_ID: "client-a-tenant"
      AZURE_OPENAI_ENDPOINT: "https://client-a-ai.openai.azure.com"
    ports:
      - "8001:8000"

  gateway-client-b:
    image: yui-gateway
    environment:
      TENANT_ID: "client-b-tenant"
      AZURE_OPENAI_ENDPOINT: "https://client-b-ai.openai.azure.com"
    ports:
      - "8002:8000"
```

### ケース 5-2: ハイブリッドクラウド環境

**状況**: オンプレミスとクラウドを組み合わせたAI環境

**解決**: モデルルーティングで適切なバックエンドを選択
- **機密データ**: オンプレミスのOllama/llama.cpp
- **一般タスク**: Azure OpenAI
- **コスト重視**: OpenAI API
- **特殊モデル**: カスタムエンドポイント

## 導入効果

### セキュリティ向上
- **APIキー管理不要**: 90%の情報漏洩リスク減
- **細かいアクセス制御**: Entra IDのRBAC活用
- **監査証跡**: 全アクセスの記録と追跡

### 運用効率
- **ワンクリックセットアップ**: 15分から1分へ短縮
- **コード変更不要**: 既存OpenAIコードをそのまま活用
- **中央管理**: チーム全体のAI環境の統合管理

### コスト最適化
- **使用量可視化**: リアルタイムコスト監視
- **モデル選択最適化**: タスク別の最適モデル選択
- **リソース共有**: チーム内での効率的なリソース活用
