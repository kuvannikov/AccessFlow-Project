# AccessFlow — первый рабочий этап

На этом этапе HR входит через Keycloak, создаёт карточки сотрудников и видит их в списке после обновления страницы. Создание карточки не создаёт учётную запись в Keycloak.

## Подготовка

Нужны Docker Desktop, Docker Compose, Node.js 24+, pnpm 11.19.0 и uv. Команды выполняются из корня проекта, если не указано иное.

```bash
cp .env.example .env
```

Замените оба значения `replace-with-a-local-password` в локальном `.env` на разные длинные пароли из латинских букв и цифр. Файл `.env` исключён из Git. Настройки предназначены для локальной демонстрации; `localhost` в конфигурации предполагает запуск браузера и Docker на одном компьютере.

## Запуск всей системы

```bash
docker compose up --build
```

Откройте [http://localhost:8080/login](http://localhost:8080/login). Keycloak откроется на `http://localhost:8081/auth`. При первом запуске дождитесь окончания загрузки Keycloak и миграции API. Данные PostgreSQL хранятся в томе `postgres_data` и сохраняются при `docker compose down`.

Для создания демонстрационного HR в отдельном терминале:

```bash
cd backend
uv sync
uv run python ../scripts/create_test_hr.py
```

Скрипт запросит email, пароль администратора Keycloak из локального `.env` и новый пароль HR без отображения ввода. Он создаст пользователя и назначит роль `HR`; пароли не записываются в файлы проекта. Для входа используйте указанный email и пароль HR на странице Keycloak. Админ-консоль: [http://localhost:8081/auth/admin/](http://localhost:8081/auth/admin/).

Остановка:

```bash
docker compose down
```

Для удаления демонстрационных данных отдельно используйте `docker compose down -v` только если они больше не нужны.

## Режим разработки

Сначала подготовьте `.env` и запустите инфраструктуру:

```bash
docker compose up -d postgres keycloak
```

Backend в отдельном терминале:

```bash
cd backend
uv sync
cd ..
bash scripts/dev_api.sh
```

Frontend в другом терминале:

```bash
cd frontend
pnpm install
pnpm dev
```

Откройте [http://localhost:5173/login](http://localhost:5173/login). Vite передаёт `/api` на локальный FastAPI `:8000`. В Docker-сборке Nginx передаёт `/api` контейнеру API. Браузер всегда использует Keycloak на `localhost:8081/auth`. Backend в контейнере получает ключи проверки по `keycloak:8080/auth`, а при локальном запуске — по `localhost:8081/auth`. В обоих случаях он проверяет издателя токена `http://localhost:8081/auth/realms/accessflow`.

`pnpm dev` слушает только `127.0.0.1`. Если доступ к Vite с другого устройства действительно нужен, запустите `pnpm exec vite --host 0.0.0.0` и отдельно настройте адреса Keycloak для этого устройства.

## Проверки

```bash
cd backend
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
cd ../frontend
pnpm test
pnpm build
```

Открытый `GET /api/health` проверяет только работу процесса API (liveness). `GET /api/ready` выполняет `SELECT 1` в PostgreSQL: при доступной БД возвращает 200, иначе 503 без строки подключения. Остальные маршруты `/api/me`, `/api/employees`, `DELETE /api/employees/{id}` и `/api/employees/slug-suggestion` требуют Bearer access token с ролью `HR`.

Интеграционные тесты запускайте только с отдельным именем Compose-проекта, когда обычный стек не занимает его локальные порты. Из корня проекта:

```bash
docker compose -p accessflow_integration up --build -d
set -a
source .env
set +a
cd backend
ACCESSFLOW_INTEGRATION=1 uv run --frozen pytest -q tests/test_integration.py
cd ..
docker compose -p accessflow_integration down
```

Тесты создают только тестовые учётные записи и карточки в отдельном томе `accessflow_integration_postgres_data`; команда `down` не удаляет том.

Логи API выводятся в терминал локального запуска и доступны через `docker compose logs -f api`. По умолчанию уровень `INFO`; в `.env` можно указать `LOG_LEVEL=DEBUG`, `WARNING` или `ERROR`. В каждой строке API есть `request_id`, а ответ содержит заголовок `X-Request-ID`. При внутренней ошибке этот ID также есть в безопасном JSON-ответе: найдите его в логах, например `docker compose logs api | rg 'request_id=<ID>'`. Метод, шаблон маршрута, статус и время запроса записываются без заголовков, тел запросов и данных сотрудников. Docker хранит не более трёх файлов логов по 10 МБ на сервис.

## Как работает вход и сохранение

На `/login` кнопка запускает OpenID Connect Authorization Code Flow с PKCE `S256` для публичного клиента `accessflow-web`. Форму email и пароля показывает Keycloak. После входа браузер переходит на `/hr` и отправляет access token в API. FastAPI получает публичный ключ Keycloak, проверяет подпись RS256, `issuer`, `audience=accessflow-api`, срок действия и роль `HR`. Проверка в интерфейсе только управляет отображением; решение о доступе принимает API.

При добавлении сотрудника форма запрашивает свободный slug. Например, `Вася Иванов` даёт `vasya.ivanov`, следующее совпадение — `vasya.ivanov-2`. API валидирует поля и уникальность; ограничения PostgreSQL защищают от одновременного создания одинаковых slug и email. Alembic создаёт таблицу при запуске API. После сохранения новая строка сразу появляется в списке, а при обновлении браузера снова загружается из PostgreSQL.

Чтобы удалить карточку, нажмите «Удалить» в строке сотрудника и подтвердите действие. API возвращает 204 при успехе и 404, если карточки уже нет. Удаление необратимо и касается только записи в PostgreSQL; учётная запись в Keycloak не удаляется.

Для автоматического slug поддерживаются латинские, русские, украинские и белорусские буквы, цифры, пробелы, дефисы и апострофы. Регистр не учитывается; разделители превращаются в дефис. Буквы других алфавитов и неподдерживаемые символы дают ошибку вместо молчаливого изменения имени. Если slug успели занять, форма сохраняет введённые данные, предлагает новый адрес и просит повторить сохранение.

Realm и клиент находятся в `keycloak/realm.json`. Импорт применяется при первом создании базы Keycloak. Если вы меняете realm после первого запуска, внесите изменение через админ-консоль либо пересоздайте демонстрационный том данных.
