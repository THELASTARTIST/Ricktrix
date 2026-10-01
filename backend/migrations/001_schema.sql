-- RICKTRIX schema
--
-- Apply in the Supabase SQL editor, or with:  psql "$SUPABASE_URL" -f 001_schema.sql
-- Safe to re-run: every statement is idempotent.
--
-- Design notes:
--  * `area` is stored on the route rather than derived in SQL, because the
--    classification is a set of regexes ported from all_routes.html and it
--    should be computed once at seed time, not re-evaluated per query.
--  * `key` is the "from|to" string the frontend already uses for bookmarks in
--    localStorage. Keeping it as a real column means existing saved routes
--    still resolve after the move to a server.
--  * The fares are user-provided and unverified (see autofare.js), so
--    fare_source and status exist to make that provenance visible.

-- ---------------------------------------------------------------- tables

create table if not exists stops (
  id         bigint generated always as identity primary key,
  name       text not null unique,
  slug       text unique,
  lat        double precision,   -- not present in the source dataset
  lng        double precision    -- not present in the source dataset
);

create table if not exists routes (
  id          int primary key,               -- preserve source ids 1..137
  from_stop_id bigint not null references stops(id),
  to_stop_id   bigint not null references stops(id),
  fare_inr     int not null check (fare_inr > 0),
  fare_source  text,
  flag         text,
  area         text,
  key          text unique,
  status       text not null default 'published'
                check (status in ('pending', 'published', 'rejected')),
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create index if not exists routes_from_idx    on routes (from_stop_id);
create index if not exists routes_to_idx      on routes (to_stop_id);
create index if not exists routes_fare_idx    on routes (fare_inr);
create index if not exists routes_area_idx    on routes (area);
create index if not exists routes_status_idx  on routes (status);

-- The `via` array from autofare.js, normalised so it can be queried.
create table if not exists route_via (
  route_id int    not null references routes(id) on delete cascade,
  stop_id  bigint not null references stops(id),
  position int    not null,
  primary key (route_id, position)
);

-- Versioned because the government tariff changes; the old row stays valid
-- history for any fare checked against it.
create table if not exists tariffs (
  id                     int generated always as identity primary key,
  effective_from         date not null,
  minimum_fare_inr       numeric(6,2) not null,
  per_km_inr             numeric(6,2) not null,
  night_surcharge_percent int,
  night_hours            text,
  source                 text,
  note                   text,
  created_at             timestamptz not null default now()
);

-- ---------------------------------------------------------------- user data
-- auth.users is Supabase's own table; these hang off it.

create table if not exists profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  handle      text unique not null,
  display_name text,
  created_at  timestamptz not null default now()
);

-- Replaces the `ricktrix-saved` localStorage array.
create table if not exists bookmarks (
  user_id    uuid not null references auth.users(id) on delete cascade,
  route_id   int  not null references routes(id)  on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, route_id)
);

create table if not exists route_submissions (
  id          bigint generated always as identity primary key,
  user_id     uuid references auth.users(id) on delete set null,
  from_name   text not null,
  to_name     text not null,
  fare_inr    int check (fare_inr is null or fare_inr > 0),
  note        text check (note is null or char_length(note) <= 1000),
  status      text not null default 'pending'
                check (status in ('pending', 'approved', 'rejected')),
  created_at  timestamptz not null default now(),
  reviewed_at timestamptz
);

create index if not exists submissions_status_idx
  on route_submissions (status, created_at desc);

-- ---------------------------------------------------------------- RLS
-- Everything here is public read / authenticated write. The moderation queue
-- is reachable only with the service-role key, which bypasses RLS.

alter table stops             enable row level security;
alter table routes            enable row level security;
alter table route_via         enable row level security;
alter table tariffs           enable row level security;
alter table profiles          enable row level security;
alter table bookmarks         enable row level security;
alter table route_submissions enable row level security;

drop policy if exists stops_read on stops;
create policy stops_read on stops for select using (true);

drop policy if exists routes_read on routes;
create policy routes_read on routes for select
  using (status = 'published' or auth.uid() is not null);

drop policy if exists route_via_read on route_via;
create policy route_via_read on route_via for select using (true);

drop policy if exists tariffs_read on tariffs;
create policy tariffs_read on tariffs for select using (true);

drop policy if exists profiles_self on profiles;
create policy profiles_self on profiles for all
  using (auth.uid() = id) with check (auth.uid() = id);

-- Users manage only their own bookmarks.
drop policy if exists bookmarks_self on bookmarks;
create policy bookmarks_self on bookmarks for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Anyone may submit, including signed out; nobody may read the queue.
drop policy if exists submissions_insert on route_submissions;
create policy submissions_insert on route_submissions for insert
  with check (true);

-- ---------------------------------------------------------------- RPCs
-- app/data_source.py calls these by name via PostgREST.

create or replace function find_routes(
  q_text  text default null,
  q_area  text default null,
  q_sort  text default 'default',
  q_limit int default 100,
  q_offset int default 0
)
returns setof jsonb
language sql stable
as $$
  select jsonb_build_object(
    'id',    r.id,
    'name',  f.name || ' ↔ ' || t.name,
    'from',  f.name,
    'to',    t.name,
    'fare',  r.fare_inr,
    'via',   coalesce((
              select jsonb_agg(s.name order by v.position)
              from route_via v join stops s on s.id = v.stop_id
              where v.route_id = r.id
            ), '[]'::jsonb),
    'area',  coalesce(r.area, 'Central Kolkata'),
    'key',   r.key
  )
  from routes r
  join stops f on f.id = r.from_stop_id
  join stops t on t.id = r.to_stop_id
  where r.status = 'published'
    and (q_text is null or
         f.name ilike '%' || q_text || '%' or
         t.name ilike '%' || q_text || '%' or
         exists (select 1 from route_via v join stops s on s.id = v.stop_id
                 where v.route_id = r.id and s.name ilike '%' || q_text || '%'))
    and (q_area is null or r.area = q_area)
  order by
    case when q_sort = 'fareAsc'  then r.fare_inr end asc nulls last,
    case when q_sort = 'fareDesc' then r.fare_inr end desc nulls last,
    case when q_sort = 'az'       then f.name end asc nulls last,
    r.id
  limit greatest(1, least(q_limit, 500))
  offset greatest(0, q_offset);
$$;

create or replace function popular_stops(n int default 8)
returns setof jsonb
language sql stable
as $$
  with counts as (
    select s.name, count(*) as n
    from stops s
    left join route_via v on v.stop_id = s.id
    group by s.id, s.name
  )
  select jsonb_build_object('name', name, 'count', n)
  from counts order by n desc, name asc limit greatest(1, least(n, 50));
$$;

create or replace function route_stats()
returns setof jsonb
language sql stable
as $$
  select jsonb_build_object(
    'routes',       (select count(*) from routes where status = 'published'),
    'stops',        (select count(*) from stops),
    'areas',        coalesce((select jsonb_agg(distinct area order by area)
                              from routes where status = 'published'), '[]'::jsonb),
    'fare_min_inr', (select min(fare_inr) from routes where status = 'published'),
    'fare_max_inr', (select max(fare_inr) from routes where status = 'published')
  );
$$;
