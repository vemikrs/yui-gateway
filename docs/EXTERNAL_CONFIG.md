# 外部設定ファイルの使用方法

YuiGatewayはYAML形式の外部設定ファイルをサポートしており、モデル名やプラグイン設定をコード外で管理できます。

## 初期設定

`config.yaml` が存在しない場合、YuiGatewayは初回起動時に自動的に生成します：

```bash
# 初回起動時、config.yamlが自動生成される
bash scripts/start_local.sh
```

生成されたファイルは `config.yaml.template` の内容をコピーします。テンプレートが存在しない場合は、ミニマルな設定が自動生成されます。

## 設定ファイルの編集

生成された `config.yaml` を編集してカスタマイズできます：

```yaml
# config.yaml の例

core:
  environment: production
  log_level: INFO

  azure_openai:
    endpoint: ${AZURE_OPENAI_ENDPOINT}  # 環境変数から読み込み
    api_version: "2024-10-21"

    # サポートするモデルのリスト
    available_models:
      - gpt-5-mini
      - gpt-4o
      - gpt-35-turbo

  auth:
    tenant_id: ${TENANT_ID}
    client_id: ${CLIENT_ID}
    client_secret: ${CLIENT_SECRET}
    scope: https://cognitiveservices.azure.com/.default

plugins:
  # A5M2互換ミドルウェア（オプション）
  a5m2_compatibility:
    enabled: false  # 必要に応じてtrueに変更
    model_aliases:
      gpt-4: gpt-5-mini
      gpt-3.5-turbo: gpt-35-turbo
```

## 環境変数の展開

設定ファイル内で `${ENV_VAR_NAME}` 形式を使用すると、環境変数が自動的に展開されます：

```yaml
auth:
  tenant_id: ${TENANT_ID}  # .envファイルの値が使用される
  client_id: ${CLIENT_ID}
```

## 設定の優先順位

設定は以下の優先順位で適用されます（後の方が優先）：

1. コード内のデフォルト値
2. 外部設定ファイル（config.yaml）
3. 環境変数（.env）

## モデル設定の例

### 基本設定

```yaml
core:
  azure_openai:
    available_models:
      - gpt-5-mini
      - gpt-4o
```

### カスタムデプロイメント名

```yaml
core:
  azure_openai:
    available_models:
      - my-custom-gpt4-deployment
      - my-custom-gpt35-deployment
      - experimental-model-v1
```

### 環境変数を使った動的設定

```yaml
core:
  azure_openai:
    available_models:
      - ${PRIMARY_MODEL}   # 例: gpt-5-mini
      - ${SECONDARY_MODEL} # 例: gpt-4o
      - gpt-35-turbo       # 固定値
```

## プラグイン設定の例

### A5M2互換機能を有効化

```yaml
plugins:
  a5m2_compatibility:
    enabled: true
    model_aliases:
      # A5M2が送信するモデル名 → 実際のデプロイメント名
      gpt-4: my-gpt4-deployment
      gpt-4-turbo: my-gpt4-turbo-deployment
      gpt-3.5-turbo: my-gpt35-deployment
```

## トラブルシューティング

### 設定ファイルが読み込まれない

ログで以下のメッセージを確認：

```
INFO: Config file not found. Creating config.yaml from template...
INFO: Created config.yaml from template
```

または：

```
INFO: Loaded configuration from config.yaml
```

### 環境変数が展開されない

環境変数が正しく設定されているか確認：

```bash
echo $AZURE_OPENAI_ENDPOINT
echo $TENANT_ID
```

警告ログも確認：

```
WARNING: Environment variable 'AZURE_OPENAI_ENDPOINT' is not set
```

### YAMLサポートが無効

PyYAMLがインストールされていない場合：

```bash
poetry install  # または
pip install pyyaml
```

## ベストプラクティス

1. **秘密情報は環境変数で管理**
   - 設定ファイルには `${ENV_VAR}` 形式で記述
   - `.env` ファイルに実際の値を保存（Gitにコミットしない）

2. **モデル名はデプロイメント名と一致させる**
   - Azureポータルで確認したデプロイメント名を使用
   - エイリアスが必要な場合のみプラグインを使用

3. **設定の検証**
   - 起動時のログで設定が正しく読み込まれたか確認
   - 環境変数が未設定の警告に注意

4. **バージョン管理**
   - `config.yaml` は `.gitignore` に含まれている（個人設定のため）
   - `config.yaml.template` をバージョン管理して共有

## config.yamlの再生成

誤って設定を壊した場合、ファイルを削除すれば再生成されます：

```bash
# 設定をリセット
rm config.yaml

# 起動時に自動再生成される
bash scripts/start_local.sh
```

または手動でテンプレートからコピー：

```bash
cp config.yaml.template config.yaml
```
