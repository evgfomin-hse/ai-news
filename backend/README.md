# Backend — HSE AI News

## Локальный запуск
Для запуска приложения нам понадобиться база данных PostgreSQL, дефолтный способ для локального запуска - запуск докер контейнера:

```bash
./infra/start-local-db.sh
```

Для запуска самого приложения - скрипты.
Для Linux/MacOS:

```bash
./infra/start.sh
```

Для Windows:

```powershell
.\infra\start.ps1
```

## Ручной запуск генерации
Для запуска ночного прогона генерации можно использовать публичный эндпоинт. Для запуска в сервисе необходим настроенный X-Summary-Job-Secret, впоследсвтии передаваемый в хедерах.

```bash
curl -X POST http://localhost:8000/tasks/summary/run-bulk -H "X-Summary-Job-Secret: ItsASecretIConfiguredInEnv"
```

Пример запуска:
```bash
evgen@tokyo MINGW64 ~/repos/ai-news-hse (stable)
$ curl -X POST http://localhost:8000/tasks/summary/run-bulk     -H "X-Summary-Job-Secret: somesecret"
{"users_total":1,"users_processed":1,"skipped_no_interests":0,"digest_failed":0,"news_articles_fetched":76,"keyword_extraction_failed":0,"telegram_sent":0,"telegram_skipped_no_config":1,"telegram_failed":0,"telegram_no_sender":0}
```

## Тесты
