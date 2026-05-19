# Douner AI - 東亜大学向けLMS・学内情報RAGサービス

Douner AIは、東亜大学の公告・学科情報・案内文書をもとに、学生が自然言語で質問できる **RAG（Retrieval-Augmented Generation）ベースのAI相談サービス**です。

単純なLLMチャットボットではなく、収集した学内情報をMySQLとChromaDBに保存し、ユーザーの質問に関連する文書を検索した上で、Groq LLMを用いて回答を生成する構成になっています。

---

## プロジェクト概要

本サービスは、東亜大学の学生が授業情報、学内案内、学科公告、生活情報などを自然言語で質問し、必要な情報へ素早くアクセスできるようにすることを目的としています。

### 開発目的

- 学内公告や案内文書を探す手間を減らす
- 正確なキーワードを知らなくても自然言語で質問できるようにする
- 大学固有の情報に基づいた回答を生成する
- 回答に参考資料のタイトルやURLを表示する
- 韓国語、日本語、英語、中国語などの多言語回答に対応する

---

## 主な機能

- 東亜大学に関する質問へのAI自動回答
- 東亜大学公告・学科公告のクローリング
- PDF案内文書をもとにしたRAG検索
- 会員登録 / ログイン
- チャット履歴保存
- 回答に参考文書タイトル・URLを表示
- Docker Composeによるマルチコンテナ構成
- Nginx Reverse Proxy適用
- GCP Compute Engine上でのデプロイ検証

---

## アーキテクチャ

```text
User Browser
    |
    | HTTP :80
    v
Nginx Reverse Proxy
    |
    | /api request
    v
FastAPI Backend
    |
    | Login / Signup / Question API
    v
RAG Service
    |
    | Question Embedding
    v
ChromaDB Vector Search
    |
    | Retrieve relevant context
    v
Groq LLM
    |
    | Generate answer
    v
User Browser
```

---

## RAG処理フロー

```text
公告 / PDF案内文書
    |
    v
crawler.py / ingest script
    |
    v
MySQLにnotices / documentsを保存
    |
    v
context chunkを作成
    |
    v
HuggingFace Embedding
    |
    v
ChromaDBに保存
    |
    v
ユーザーが質問を入力
    |
    v
質問をEmbedding
    |
    v
ChromaDBで類似文書を検索
    |
    v
検索されたcontext + 質問をGroq LLMへ渡す
    |
    v
回答 + 参考資料を返却
```

---

## 技術スタック

### LLM / RAG

- Groq API
- LLaMA 3.3 70B
- HuggingFace Embeddings
- jhgan/ko-sroberta-multitask
- ChromaDB

### Backend

- Python
- FastAPI
- Uvicorn

### Database

- MySQL 8.0

### Infrastructure

- Docker
- Docker Compose
- Nginx Reverse Proxy
- GCP Compute Engine
- Ubuntu Server

### Crawling / Data Processing

- requests
- BeautifulSoup4
- PyMuPDF
- LangChain Text Splitter

---

## 担当範囲

本プロジェクトでは、主にバックエンド・インフラ領域を担当しました。

- RAG構成の設計
- FastAPIによるAPIサーバー実装
- ChromaDB連携
- 東亜大学公告クローラー実装
- PDFおよび公告文書のcontext chunk処理
- Docker Composeによる実行環境構築
- GCP Compute Engine上でのデプロイ検証
- Nginx Reverse Proxy設定
- Dockerビルド時のディスク容量不足に対するトラブルシューティング

---

## 技術選定理由

### RAGを採用した理由

LLM単体では、大学固有の情報や更新される学内公告に対して、不正確な回答を生成する可能性があります。  
そのため、学内情報をベクトル化してChromaDBに保存し、ユーザーの質問に関連する情報を検索してからLLMに渡すRAG構成を採用しました。

### Docker Composeを採用した理由

APIサーバー、DB、ChromaDB、Nginxなど複数のコンテナを一括で管理し、同じ手順で環境を再現できるようにするためにDocker Composeを利用しました。

### GCP Compute Engineを利用した理由

Cloud Runのようなマネージドサービスも便利ですが、今回はLinux、Docker、Nginx、Firewall、リソース管理を自分で設定し、インフラの基礎を理解することを重視したため、GCP Compute Engineを利用しました。

---

## トラブルシューティング経験

### Dockerビルド時のディスク容量不足

Dockerビルド中に以下のエラーが発生しました。

```text
No space left on device
```

原因確認のため、以下のコマンドを使用しました。

```bash
df -h
docker system df
```

確認した結果、Dockerイメージやビルドキャッシュがディスク容量を圧迫していることが分かりました。

一時的にキャッシュを削除するだけでは再発する可能性があるため、GCP Persistent Diskを拡張し、Linux側でファイルシステム拡張を行いました。

```bash
sudo resize2fs
```

この経験を通じて、AIサービスでは機能実装だけでなく、リソース管理やインフラ設計も重要であることを学びました。

---

## 実行方法

### 1. 環境変数設定

```bash
cp .env.example .env
```

`.env`に必要なAPI KeyやDB設定を記述します。

```env
GROQ_API_KEY=your_groq_api_key
DB_HOST=db
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=your_database
```

### 2. Docker Compose起動

```bash
docker compose up -d --build
```

### 3. コンテナ確認

```bash
docker ps
```

### 4. ログ確認

```bash
docker compose logs
```

---

## Demo

現在、検証環境としてGCP Compute Engine上で実行しています。

- Demo URL: http://34.64.196.94/

現在はStatic IPで公開しており、今後は独自ドメイン設定とHTTPS化を行う予定です。

---

## 今後の改善予定

- 独自ドメイン設定
- HTTPS化
- Cloud Logging / Monitoring連携
- 管理者ページ追加
- chunk分割戦略の改善
- ChromaDB検索精度の改善
- Cloud Run または GKEへの一部移行検討
- Kubernetesを用いたデプロイ構成の学習・検証

---

## 学んだこと

このプロジェクトを通じて、AI機能を実装するだけでなく、サービスを安定して動かすためには、バックエンド、DB、ベクトル検索、LLM、Docker、Nginx、クラウドインフラを一体として考える必要があると学びました。

特にDocker Composeは、検証環境では複数コンテナを素早く管理できる一方で、大規模運用では自動復旧、オートスケーリング、複数ノード管理に限界があると理解しました。今後はKubernetesやGKEを学習し、より拡張性のある構成を検証していきたいと考えています。
