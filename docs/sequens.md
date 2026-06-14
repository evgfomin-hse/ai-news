# Диаграммы последовательностей (Mermaid)

## Ф1. Задать интересы свободным текстом

```mermaid
sequenceDiagram
    actor U as Пользователь
    participant FE as Frontend (SPA)
    participant API as API /interests
    participant SVC as InterestService
    participant REPO as InterestRepository
    participant DB as PostgreSQL

    U->>FE: Ввести текст интересов и сохранить
    FE->>API: PATCH /interests (cookie)<br/>{ interests: "<текст>" }
    API->>API: get_current_user → User
    API->>SVC: upsert_for_user(user.id, interests_text)
    SVC->>REPO: upsert(user_id, interests)
    REPO->>DB: INSERT/UPDATE interests
    DB-->>REPO: row (id, interests)
    REPO-->>SVC: Interest
    SVC-->>API: row
    API-->>FE: 200 InterestOut { interestId, interests }
    FE-->>U: Подтверждение сохранения
```

---

## Ф2. Изменить ранее заданные интересы

```mermaid
sequenceDiagram
    actor U as Пользователь
    participant FE as Frontend (SPA)
    participant API as API /interests
    participant SVC as InterestService
    participant REPO as InterestRepository
    participant DB as PostgreSQL

    U->>FE: Открыть страницу интересов
    FE->>API: GET /interests (cookie)
    API->>SVC: get_latest_for_user(user.id)
    SVC->>REPO: get_latest_for_user(user_id)
    REPO->>DB: SELECT latest interests
    DB-->>REPO: row | none
    REPO-->>SVC: Interest | None
    SVC-->>API: row | None
    API-->>FE: 200 InterestOut (текущий текст)
    FE-->>U: Показать текущие интересы

    U->>FE: Отредактировать и сохранить
    FE->>API: PATCH /interests { interests: "<новый текст>" }
    API->>SVC: upsert_for_user(user.id, new_text)
    SVC->>REPO: upsert(user_id, new_text)
    REPO->>DB: UPDATE interests
    DB-->>REPO: row
    REPO-->>SVC: Interest
    SVC-->>API: row
    API-->>FE: 200 InterestOut { interestId, interests }
    FE-->>U: Подтверждение изменения
```

---

## Ф3. Отобразить персональную ленту сводок

```mermaid
sequenceDiagram
    actor U as Пользователь
    participant FE as Frontend (SPA)
    participant API as API /summary
    participant SVC as PostgresSummaryService
    participant REPO as SummaryRepository
    participant DB as PostgreSQL

    U->>FE: Открыть ленту сводок
    FE->>API: GET /summary?page=1&page_size=20 (cookie)
    API->>API: get_current_user → User
    API->>SVC: get_summary_for_user(user.id, page, page_size)
    SVC->>REPO: count_for_user(user_id)
    REPO->>DB: SELECT count(*)
    DB-->>REPO: total
    REPO-->>SVC: total
    alt total == 0
        SVC-->>API: UserSummaryResponse(items=[], notice="No summaries yet")
    else есть строки
        SVC->>REPO: list_page_for_user(user_id, offset, limit)
        REPO->>DB: SELECT ... ORDER BY created_at LIMIT/OFFSET
        DB-->>REPO: rows
        REPO-->>SVC: rows
        SVC-->>API: UserSummaryResponse(items, total, page, total_pages, generated_at)
    end
    API-->>FE: 200 UserSummaryResponse
    FE-->>U: Рендер markdown-ленты с пагинацией
```

---

## Ф4. Открыть исходные материалы, связанные со сводкой

```mermaid
sequenceDiagram
    actor U as Пользователь
    participant FE as Frontend (SPA)
    participant EXT as Внешний новостной сайт

    Note over FE: Лента уже получена (Ф3) —<br/>в markdown-теле сводки есть ссылки на источники
    U->>FE: Кликнуть ссылку на источник в сводке
    FE->>EXT: Открыть URL новости в новой вкладке
    EXT-->>U: Исходная статья (оригинал)
```

---

## Ф5. Учитывать оценки при последующей подготовке материалов

```mermaid
sequenceDiagram
    participant JOB as Ночной job / run-bulk
    participant MNT as SummaryMaintenanceService
    participant SREPO as ScoreRepository
    participant PROMPT as build_summary_prompt
    participant LLM as LM Studio (qwen3-4b)
    participant SUMREPO as SummaryRepository
    participant DB as PostgreSQL

    JOB->>MNT: run_bulk_for_all_users()
    loop для каждого пользователя с интересами
        MNT->>SREPO: list_recent_for_user(user_id, limit=10)
        SREPO->>DB: SELECT последние оценки
        DB-->>SREPO: scored summaries
        SREPO-->>MNT: recent_scores
        MNT->>PROMPT: score_signals_from_rows(recent_scores)
        Note over PROMPT: лайки/дизлайки с описанием<br/>добавляются в промпт как сигналы предпочтений
        PROMPT-->>MNT: prompt (учитывает прошлые оценки)
        MNT->>LLM: generate(prompt)
        LLM-->>MNT: персонализированная сводка
        MNT->>SUMREPO: append_row(user_id, summary)
        SUMREPO->>DB: INSERT summaries
    end
```

---

## Ф6. Принять пользовательскую оценку сводки

```mermaid
sequenceDiagram
    actor U as Пользователь
    participant FE as Frontend (SPA)
    participant API as API /score
    participant SVC as ScoreService
    participant SUMREPO as SummaryRepository
    participant SREPO as ScoreRepository
    participant DB as PostgreSQL

    U->>FE: Нажать 👍/👎 (опц. комментарий)
    FE->>API: PUT /score (cookie)<br/>{ summary_id, value, description }
    API->>API: get_current_user → User
    API->>SVC: upsert_for_user(user.id, request)
    SVC->>SUMREPO: exists_for_user(summary_id, user_id)
    SUMREPO->>DB: SELECT exists
    DB-->>SUMREPO: bool
    alt сводка не принадлежит пользователю
        SUMREPO-->>SVC: false
        SVC-->>API: SummaryNotFoundError
        API-->>FE: 404 Summary not found
    else сводка существует
        SUMREPO-->>SVC: true
        SVC->>SREPO: upsert(request, now)
        SREPO->>DB: INSERT/UPDATE scores
        DB-->>SREPO: row
        SREPO-->>SVC: Score
        SVC-->>API: Score
        API-->>FE: 200 ScoreOut { id, summary_id, value, description }
    end
    FE-->>U: Подтверждение оценки
```

---

## Ф7. Доставить подготовленные сводки по выбранному каналу (Telegram)

```mermaid
sequenceDiagram
    participant MNT as SummaryMaintenanceService
    participant SUMREPO as SummaryRepository
    participant TSVC as TransportService
    participant SENDER as TelegramSender
    participant TG as Telegram Bot API
    participant DB as PostgreSQL

    Note over MNT: сводка для пользователя уже сгенерирована
    MNT->>SUMREPO: append_row(user_id, summary)
    SUMREPO->>DB: INSERT summaries
    MNT->>TSVC: get_active_for_user(user_id)
    TSVC->>DB: SELECT transport
    DB-->>TSVC: transport row
    TSVC-->>MNT: token, chat_id
    alt токен или chat_id не настроены
        MNT-->>MNT: outcome = skipped_no_config
    else канал настроен
        MNT->>SENDER: send(token, chat_id, text=summary)
        SENDER->>TG: POST /bot<token>/sendMessage
        alt успех
            TG-->>SENDER: ok, message_id
            SENDER-->>MNT: message_id (outcome = sent)
        else ошибка доставки
            TG-->>SENDER: error
            SENDER-->>MNT: TelegramSendError (outcome = failed, логируется)
        end
    end
```

---

## Ф8. Экспортировать историю сводок в CSV

```mermaid
sequenceDiagram
    actor U as Пользователь
    participant FE as Frontend (SPA)
    participant API as API /summary/export.csv
    participant REPO as SummaryRepository
    participant EXP as build_summaries_csv
    participant DB as PostgreSQL

    U->>FE: Нажать «Экспорт CSV»
    FE->>API: GET /summary/export.csv (cookie)
    API->>API: get_current_user → User
    API->>REPO: list_all_with_scores_for_user(user.id)
    REPO->>DB: SELECT summaries LEFT JOIN scores
    DB-->>REPO: rows
    REPO-->>API: rows
    API->>EXP: build_summaries_csv(rows)
    Note over EXP: колонки summary_id, created_at_utc,<br/>body, score, score_description
    EXP-->>API: csv_text
    API-->>FE: 200 text/csv (attachment: summaries-YYYY-MM-DD.csv)
    FE-->>U: Скачивание файла
```

---

## Ф9. Получать новости из активных источников

```mermaid
sequenceDiagram
    participant JOB as Ночной job / run-bulk
    participant MNT as SummaryMaintenanceService
    participant KW as KeywordExtractor
    participant LLM as LM Studio (qwen3-4b)
    participant FETCH as NewsApiFetcherService
    participant NAPI as NewsAPI /everything
    participant SCRAPE as trafilatura (скрейпинг)
    participant NREPO as NewsRepository
    participant DB as PostgreSQL

    JOB->>MNT: run_bulk_for_all_users()
    MNT->>KW: extract(интересы всех пользователей)
    KW->>LLM: generate(prompt с интересами)
    LLM-->>KW: ключевые слова
    KW-->>MNT: query
    MNT->>FETCH: fetch_and_store(query, start, end)
    loop постранично (page/pageSize), пока < max_articles
        FETCH->>NAPI: GET /everything?q&from&to&page (X-Api-Key)
        NAPI-->>FETCH: articles[], totalResults
        Note over FETCH: maximumResultsReached →<br/>стоп без ошибки (free-плэн = 100)
    end
    FETCH->>SCRAPE: дообогащение полным текстом (параллельно)
    SCRAPE-->>FETCH: content
    FETCH->>NREPO: insert_many(articles)
    NREPO->>DB: INSERT news_articles
    DB-->>NREPO: inserted count
    NREPO-->>FETCH: count
    FETCH-->>MNT: число сохранённых статей
```

---

## Ф10. Сохранять исходные новости с метаданными

```mermaid
sequenceDiagram
    participant FETCH as NewsApiFetcherService
    participant BUILD as _article_from_payload
    participant NREPO as NewsRepository
    participant DB as PostgreSQL

    Note over FETCH: получен ответ NewsAPI (массив articles)
    loop для каждой статьи
        FETCH->>BUILD: _article_from_payload(item, now)
        Note over BUILD: метаданные NewsArticle:<br/>fetched_at, source (newsapi:everything),<br/>title, description, url, published_at
        BUILD-->>FETCH: NewsArticle | None (отсев без title/url, дубли по url)
    end
    FETCH->>NREPO: insert_many(articles[:max])
    NREPO->>DB: INSERT INTO news_articles (метаданные + content)
    DB-->>NREPO: inserted count
    NREPO-->>FETCH: count
    FETCH->>FETCH: session.commit()
```

---

## Ф11. Импортировать историю сводок из CSV

```mermaid
sequenceDiagram
    actor U as Пользователь
    participant FE as Frontend (SPA)
    participant API as API /summary/import.csv
    participant PARSE as parse_summaries_csv
    participant REPO as SummaryRepository
    participant DB as PostgreSQL

    U->>FE: Выбрать CSV и загрузить
    FE->>API: POST /summary/import.csv (cookie, multipart file)
    API->>API: get_current_user → User
    API->>API: проверка размера (≤ 5 МБ) и декод UTF-8(-sig)
    alt файл слишком большой
        API-->>FE: 413 CSV file is too large
    else не UTF-8
        API-->>FE: 400 File must be UTF-8 encoded
    else корректная кодировка
        API->>PARSE: parse_summaries_csv(text)
        alt формат нарушен
            PARSE-->>API: CsvImportError(problems)
            API-->>FE: 400 { error: invalid_csv, problems }
        else формат валиден
            PARSE-->>API: rows
            API->>REPO: insert_imported_for_user(user.id, rows)
            REPO->>DB: INSERT summaries (+ scores)
            DB-->>REPO: counts
            REPO-->>API: (summaries, scores)
            API-->>FE: 200 { summaries_imported, scores_imported }
        end
    end
    FE-->>U: Результат импорта
```

---

## Ф12. Отчёт о количестве сгенерированных сводок (за всё время и за сегодня)

Глобальные счётчики по всем пользователям; endpoint'ы без авторизации.

```mermaid
sequenceDiagram
    actor U as Пользователь
    participant FE as Frontend (SPA)
    participant API as API /summary/stats
    participant REPO as SummaryRepository
    participant DB as PostgreSQL

    U->>FE: Открыть страницу со статистикой
    par Сводки за сегодня
        FE->>API: GET /summary/stats/today
        API->>REPO: count_created_today()
        REPO->>DB: SELECT count(*) WHERE created_at >= начало дня
        DB-->>REPO: today
        REPO-->>API: today
        API-->>FE: 200 { stories_today }
    and Сводки за всё время
        FE->>API: GET /summary/stats/all-time
        API->>REPO: count_all()
        REPO->>DB: SELECT count(*)
        DB-->>REPO: all_time
        REPO-->>API: all_time
        API-->>FE: 200 { stories_all_time }
    end
    FE-->>U: Показать «сегодня» и «за всё время»
```
