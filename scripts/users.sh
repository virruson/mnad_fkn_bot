#!/usr/bin/env bash
# Участники бота: сводка и список. Запускать на сервере из любой папки проекта.
#
#   ./scripts/users.sh              сводка + список (список листается: q — выход)
#   ./scripts/users.sh summary      только сводка
#   ./scripts/users.sh list         только список
#   ./scripts/users.sh csv > users.csv   список в CSV (для Excel)
#
# «вериф = f» — вышел через «🚪 Выйти»: запись и настройки остаются, но ему ничего не приходит.
# Флаги уведомлений в сводке считаются только по авторизованным.
set -euo pipefail
cd "$(dirname "$0")/.."

DB_USER=mnad_bot
DB_NAME=mnad_schedule
if [ -f .env ]; then
    DB_USER=$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2- | tr -d '"'"'" || true); DB_USER=${DB_USER:-mnad_bot}
    DB_NAME=$(grep -E '^POSTGRES_DB=' .env | cut -d= -f2- | tr -d '"'"'" || true);   DB_NAME=${DB_NAME:-mnad_schedule}
fi

psql_run() {   # SQL из stdin; без предупреждения docker-compose про `version`
    docker-compose exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" "$@" 2> >(grep -v "is obsolete" >&2)
}

SUMMARY_SQL="
select count(*)                                                        as всего,
       count(*) filter (where is_verified)                             as вериф,
       count(*) filter (where created_at > now() - interval '7 days')  as новых_7дн,
       count(*) filter (where last_login > now() - interval '7 days')  as заходили_7дн,
       count(*) filter (where is_verified and news_enabled)            as новости,
       count(*) filter (where is_verified and deadlines_enabled)       as дедлайны,
       count(*) filter (where is_verified and digest_enabled)          as расписание,
       count(*) filter (where is_verified and reminders_enabled)       as напом_15мин,
       count(*) filter (where is_verified and not common_enabled)      as без_общих
from users;"

LIST_SQL="
select u.id, u.telegram_id as tg, u.email, u.full_name as имя,
       coalesce('@'||u.username,'') as ник,
       u.is_verified as вериф,
       to_char(u.created_at,'DD.MM HH24:MI') as с,
       to_char(u.last_login,'DD.MM HH24:MI') as вход,
       concat_ws(' ', case when u.news_enabled then 'новости' end,
                      case when u.deadlines_enabled then 'дедл' end,
                      case when u.digest_enabled then 'расп' end,
                      case when u.reminders_enabled then '15мин' end) as уведомления,
       u.common_enabled as общие,
       (select string_agg(coalesce(nullif(s.short_name,''), s.name), ', ' order by s.name)
          from user_electives ue join subjects s on s.id = ue.subject_id
         where ue.user_id = u.id) as маголего,
       (select name from modules where id = u.view_module_id) as смотрит_модуль,
       (select count(*) from user_progress p where p.user_id = u.id) as отметок,
       (select count(*) from feedback f where f.user_id = u.id)      as обращений,
       u.thanks_count as сердечек
from users u
order by u.created_at;"

case "${1:-all}" in
    summary) echo "$SUMMARY_SQL" | psql_run ;;
    list)    echo "$LIST_SQL" | psql_run | less -S ;;
    csv)     echo "$LIST_SQL" | psql_run --csv ;;
    all)     { echo "$SUMMARY_SQL" | psql_run; echo "$LIST_SQL" | psql_run; } | less -S ;;
    *)       echo "Использование: $0 [summary|list|csv]" >&2; exit 1 ;;
esac
