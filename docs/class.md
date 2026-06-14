# AI News HSE - UML 2.5.1 Class Diagram

```mermaid
classDiagram
    direction LR

    %% ============================================================
    %% External / infrastructure types
    %% ============================================================
    class Session {
        <<external>>
    }
    class Callable {
        <<external>>
    }
    class DateTime {
        <<dataType>>
    }
    class JsonObject {
        <<dataType>>
    }
    class List {
        <<dataType>>
    }
    class Tuple {
        <<dataType>>
    }
    class Dictionary {
        <<dataType>>
    }
    class Iterable {
        <<interface>>
    }
    class SendErrorKind {
        <<enumeration>>
        network
        non_json
        telegram_error
        missing_message_id
    }

    %% ============================================================
    %% Domain entities (SQLAlchemy ORM) - app.models
    %% ============================================================
    class Base
    class User {
        <<entity>>
        +id : Integer
        +subject : String
        +email : String
        +name : String [0..1]
        +picture : String [0..1]
        +created_at : DateTime
    }
    class Interest {
        <<entity>>
        +id : Integer
        +user_id : Integer
        +interests : String [0..1]
        +created_at : DateTime [0..1]
        +updated_at : DateTime [0..1]
    }
    class NewsArticle {
        <<entity>>
        +id : Integer
        +fetched_at : DateTime
        +source : String
        +title : String
        +description : String [0..1]
        +url : String [0..1]
        +published_at : DateTime [0..1]
        +content : String [0..1]
    }
    class Summary {
        <<entity>>
        +id : Integer
        +user_id : Integer
        +summary : String [0..1]
        +created_at : DateTime [0..1]
    }
    class Score {
        <<entity>>
        +id : Integer
        +summary_id : Integer
        +score : Boolean [0..1]
        +description : String [0..1]
        +created_at : DateTime [0..1]
        +updated_at : DateTime [0..1]
    }
    class Transport {
        <<entity>>
        +id : Integer
        +user_id : Integer
        +data : JsonObject [0..1]
        +created_at : DateTime [0..1]
        +updated_at : DateTime [0..1]
        +deleted_at : DateTime [0..1]
    }

    Base <|-- User
    Base <|-- Interest
    Base <|-- NewsArticle
    Base <|-- Summary
    Base <|-- Score
    Base <|-- Transport

    note for Base "UML property: isAbstract = true"

    User "1" -- "0..1" Interest : has latest
    User "1" -- "0..*" Summary : owns
    Summary "1" -- "0..1" Score : has
    User "1" -- "0..*" Transport : has

    %% ============================================================
    %% Data access layer - app.repositories
    %% ============================================================
    class DatabaseRepository {
        <<repository>>
        -_session : Session
        +ping()
    }
    class UserRepository {
        <<repository>>
        -_session : Session
        +get_by_id(user_id : Integer) : User [0..1]
        +list_all_ids() : List~Integer~
        +get_or_create(subject : String, name : String, picture : String [0..1], email : String [0..1]) : User
    }
    class InterestRepository {
        <<repository>>
        -_session : Session
        +get_latest_for_user(user_id : Integer) : Interest [0..1]
        +upsert_interests(user_id : Integer, interests_text : String, now : DateTime) : Interest
    }
    class NewsRepository {
        <<repository>>
        -_session : Session
        +insert_many(articles : Iterable~NewsArticle~) : Integer
        +list_since(since : DateTime, limit : Integer) : List~NewsArticle~
        +count_since(since : DateTime) : Integer
        +list_in_window(start : DateTime, end : DateTime, limit : Integer) : List~NewsArticle~
    }
    class SummaryRepository {
        <<repository>>
        -_session : Session
        +exists_for_user(summary_id : Integer, user_id : Integer) : Boolean
        +list_all_with_scores_for_user(user_id : Integer) : List~Tuple~
        +count_for_user(user_id : Integer) : Integer
        +count_created_today() : Integer
        +count_all() : Integer
        +list_page_for_user(user_id : Integer, offset : Integer, limit : Integer) : List~Summary~
        +delete_for_user(summary_id : Integer, user_id : Integer) : Boolean
        +append_row(user_id : Integer, summary : String, created_at : DateTime)
        +insert_imported_for_user(user_id : Integer, rows : Iterable~ImportedSummary~) : Tuple
    }
    class ScoreRepository {
        <<repository>>
        -_session : Session
        +get_by_summary_id(summary_id : Integer) : Score [0..1]
        +list_recent_for_user(user_id : Integer, limit : Integer) : List~Score~
        +upsert(request : ScoreUpsertRequest, now : DateTime) : Score
    }
    class TransportRepository {
        <<repository>>
        -_session : Session
        +get_active_for_user(user_id : Integer) : Transport [0..1]
        +ensure_active_for_user(user_id : Integer, now : DateTime) : Transport
    }
    class ImportedSummary {
        <<interface>>
        +body : String
        +created_at : DateTime [0..1]
        +score : Boolean [0..1]
        +score_description : String [0..1]
        + /has_score : Boolean
    }

    DatabaseRepository ..> Session
    UserRepository ..> User
    InterestRepository ..> Interest
    NewsRepository ..> NewsArticle
    SummaryRepository ..> Summary
    SummaryRepository ..> Score
    SummaryRepository ..> ImportedSummary
    ScoreRepository ..> Score
    ScoreRepository ..> Summary
    ScoreRepository ..> ScoreUpsertRequest
    TransportRepository ..> Transport

    %% ============================================================
    %% LLM / external-IO strategy boundaries - app.services.io
    %% ============================================================
    class LLMSummarizer {
        <<interface>>
        +generate(prompt : String) : String
    }
    class ChatCompletionsSummarizer {
        <<service>>
        -_api_key : String
        -_model : String
        -_base_url : String
        -_timeout_seconds : Integer
        -_require_api_key : Boolean
        -_http_post : Callable [0..1]
        +generate(prompt : String) : String
    }
    class LLMError {
        <<exception>>
    }
    class TelegramSender {
        <<interface>>
        +send(token : String, chat_id : String, text : String) : Integer [0..1]
    }
    class RequestsTelegramSender {
        <<service>>
        -_timeout_seconds : Integer
        -_http_post : Callable
        +send(token : String, chat_id : String, text : String) : Integer [0..1]
    }
    class TelegramSendError {
        <<exception>>
        +kind : SendErrorKind
        +message : String
    }
    class NewsApiFetcherService {
        <<service>>
        -_session : Session
        -_articles : NewsRepository
        -_api_key : String
        -_language : String
        -_page_size : Integer
        -_max_articles : Integer
        -_http_get : Callable
        +fetch_and_store(query : String, start : DateTime, end : DateTime) : Integer
        -_fetch_page(query : String, start : DateTime, end : DateTime, page : Integer) : Tuple
    }
    class NewsFetchError {
        <<exception>>
    }

    ChatCompletionsSummarizer ..|> LLMSummarizer
    RequestsTelegramSender ..|> TelegramSender
    ChatCompletionsSummarizer ..> LLMError
    RequestsTelegramSender ..> TelegramSendError
    TelegramSendError ..> SendErrorKind
    NewsApiFetcherService --> NewsRepository : articles
    NewsApiFetcherService ..> NewsFetchError
    NewsApiFetcherService ..> NewsArticle

    %% ============================================================
    %% LLM-backed pipeline helpers - app.services.pipeline
    %% ============================================================
    class KeywordExtractor {
        <<service>>
        -_summarizer : LLMSummarizer
        -_max_query_chars : Integer
        +extract(users_with_interests : List~Tuple~) : String [0..1]
        -_build_prompt(non_empty : List~Tuple~) : String
        -_parse(raw : String) : List~String~
        -_format_query(keywords : List~String~) : String
    }
    class PerUserCandidateFilter {
        <<service>>
        -_summarizer : LLMSummarizer
        -_batch_size : Integer
        -_top_per_batch : Integer
        +pick_top(interests_text : String, articles : List~NewsArticle~, top_n : Integer) : List~NewsArticle~
        -_iter_batches(articles : List~NewsArticle~) : Iterable~Tuple~
        -_ask_llm_for_indices(interests_text : String, batch : List~NewsArticle~, limit : Integer) : List~Integer~ [0..1]
    }
    class SummaryPromptUtil {
        <<utility>>
        +build_summary_prompt(date_label : String, interests_text : String [0..1], recent_scores : List~ScoreSignal~, news : List~NewsItem~) : String
        +score_signals_from_rows(rows : List~Score~) : List~ScoreSignal~
        +news_items_from_rows(rows : List~NewsArticle~) : List~NewsItem~
    }
    class ScoreSignal {
        <<dataclass>>
        +value : Boolean
        +description : String [0..1]
    }
    class NewsItem {
        <<dataclass>>
        +title : String
        +description : String [0..1]
        +url : String [0..1]
        +content : String [0..1]
    }

    KeywordExtractor --> LLMSummarizer : summarizer
    PerUserCandidateFilter --> LLMSummarizer : summarizer
    PerUserCandidateFilter ..> NewsArticle
    SummaryPromptUtil ..> ScoreSignal
    SummaryPromptUtil ..> NewsItem

    %% ============================================================
    %% Application services - app.services
    %% ============================================================
    class UserService {
        <<service>>
        -_session : Session
        -_users : UserRepository
        +get_by_id(user_id : Integer) : User [0..1]
        +get_or_create(subject : String, name : String, picture : String [0..1], email : String [0..1]) : User
    }
    class InterestService {
        <<service>>
        -_session : Session
        -_interests : InterestRepository
        +get_latest_for_user(user_id : Integer) : Interest [0..1]
        +upsert_for_user(user_id : Integer, interests_text : String) : Interest
    }
    class ScoreService {
        <<service>>
        -_session : Session
        -_scores : ScoreRepository
        -_summaries : SummaryRepository
        +get_by_summary_id(summary_id : Integer) : Score [0..1]
        +get_for_user_summary(user_id : Integer, summary_id : Integer) : Score [0..1]
        +upsert_for_user(user_id : Integer, request : ScoreUpsertRequest) : Score
    }
    class SummaryNotFoundError {
        <<exception>>
    }
    class TransportService {
        <<service>>
        -_session : Session
        -_transports : TransportRepository
        +get_active_for_user(user_id : Integer) : Transport [0..1]
        +ensure_active_for_user(user_id : Integer) : Transport
        +persist_transport(row : Transport) : Transport
    }
    class HealthService {
        <<service>>
        -_database : DatabaseRepository
        +check_readiness() : HealthReport
        -_check_database() : ComponentCheck
    }
    class ComponentCheck {
        <<dataclass>>
        +component : String
        +status : String
        +observed_value_ms : Real [0..1]
        +output : String [0..1]
    }
    class HealthReport {
        <<dataclass>>
        +status : String
        +checks : List~ComponentCheck~
        + /is_healthy : Boolean
    }
    class SummaryService {
        +get_summary_for_user(user_id : Integer, page : Integer, page_size : Integer) : UserSummaryResponse
    }
    class PostgresSummaryService {
        <<service>>
        -_summaries : SummaryRepository
        +get_summary_for_user(user_id : Integer, page : Integer, page_size : Integer) : UserSummaryResponse
    }
    class MockSummaryService {
        <<service>>
        +get_summary_for_user(user_id : Integer, page : Integer, page_size : Integer) : UserSummaryResponse
    }
    class SummaryMaintenanceService {
        <<service>>
        -_session : Session
        -_summarizer : LLMSummarizer [0..1]
        -_news_fetcher : NewsApiFetcherService [0..1]
        -_keyword_extractor : KeywordExtractor [0..1]
        -_candidate_filter : PerUserCandidateFilter [0..1]
        -_telegram_sender : TelegramSender [0..1]
        +append_placeholder_for_user(user_id : Integer, force_placeholder : Boolean) : Integer
        +run_bulk_for_all_users() : Dictionary
        -_components() : Tuple
    }

    SummaryService <|-- PostgresSummaryService
    SummaryService <|-- MockSummaryService

    note for SummaryService "UML properties: isAbstract = true; get_summary_for_user.isAbstract = true"

    UserService --> UserRepository : users
    InterestService --> InterestRepository : interests
    ScoreService --> ScoreRepository : scores
    ScoreService --> SummaryRepository : summaries
    TransportService --> TransportRepository : transports
    HealthService --> DatabaseRepository : database
    PostgresSummaryService --> SummaryRepository : summaries

    SummaryMaintenanceService "1" --> "0..1" LLMSummarizer : summarizer
    SummaryMaintenanceService "1" --> "0..1" NewsApiFetcherService : newsFetcher
    SummaryMaintenanceService "1" --> "0..1" KeywordExtractor : keywordExtractor
    SummaryMaintenanceService "1" --> "0..1" PerUserCandidateFilter : candidateFilter
    SummaryMaintenanceService "1" --> "0..1" TelegramSender : telegramSender

    ScoreService ..> ScoreUpsertRequest
    ScoreService ..> SummaryNotFoundError
    HealthService ..> HealthReport
    HealthReport "1" *-- "0..*" ComponentCheck : checks
    SummaryMaintenanceService ..> UserRepository
    SummaryMaintenanceService ..> InterestRepository
    SummaryMaintenanceService ..> ScoreRepository
    SummaryMaintenanceService ..> NewsRepository
    SummaryMaintenanceService ..> SummaryRepository
    SummaryMaintenanceService ..> SummaryPromptUtil
    SummaryMaintenanceService ..> TransportService

    %% ============================================================
    %% API DTOs (Pydantic) - app.schemas
    %% ============================================================
    class ScoreUpsertRequest {
        <<DTO>>
        +summary_id : Integer
        +value : Boolean
        +description : String [0..1]
    }
    class ScoreOut {
        <<DTO>>
        +id : Integer
        +summary_id : Integer
        +value : Boolean [0..1]
        +description : String [0..1]
    }
    class SummaryItem {
        <<DTO>>
        +id : String
        +title : String
        +body : String
    }
    class UserSummaryResponse {
        <<DTO>>
        +items : List~SummaryItem~
        +total : Integer
        +page : Integer
        +page_size : Integer
        +total_pages : Integer
        +generated_at : DateTime [0..1]
        +notice : String
    }
    class UserOut {
        <<DTO>>
        +id : String
        +username : String
        +email : String
        +avatarUrl : String [0..1]
    }
    class LoginJson {
        <<DTO>>
        +user : UserOut
    }
    class InterestOut {
        <<DTO>>
        +interestId : Integer [0..1]
        +interests : String
    }
    class InterestPatch {
        <<DTO>>
        +interests : String
    }
    class TransportOut {
        <<DTO>>
        +transportId : Integer [0..1]
        +telegramConfigured : Boolean
        +telegramChatId : String [0..1]
    }
    class TransportPatch {
        <<DTO>>
        +telegramBotToken : String [0..1]
        +telegramChatId : String [0..1]
    }

    LoginJson "1" *-- "1" UserOut : user
    UserSummaryResponse "1" *-- "0..*" SummaryItem : items
    SummaryService ..> UserSummaryResponse
    PostgresSummaryService ..> UserSummaryResponse
    MockSummaryService ..> UserSummaryResponse

    %% ============================================================
    %% Pure CSV import/export - app.services.csv
    %% ============================================================
    class SummaryExportUtil {
        <<utility>>
        +build_summaries_csv(rows : Iterable~Tuple~) : String
    }
    class SummaryImportUtil {
        <<utility>>
        +parse_summaries_csv(text : String) : List~ParsedRow~
    }
    class ParsedRow {
        <<dataclass>>
        +body : String
        +created_at : DateTime [0..1]
        +score : Boolean [0..1]
        +score_description : String [0..1]
        + /has_score : Boolean
    }
    class CsvImportError {
        <<exception>>
        +problems : List~String~
    }

    ParsedRow ..|> ImportedSummary
    SummaryExportUtil ..> Summary
    SummaryExportUtil ..> Score
    SummaryImportUtil ..> ParsedRow
    SummaryImportUtil ..> CsvImportError
```
