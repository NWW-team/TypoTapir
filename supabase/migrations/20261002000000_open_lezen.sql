-- Stap 1: geen inlog meer. Iedereen met de publishable key mag de crawlresultaten
-- lezen. Schrijven blijft alleen voor de service-role key (de crawl-workflow).
--
-- LET OP: dit draait besluit 3 terug (zie OVERDRACHT.md). De publishable key staat in
-- een publieke repository, dus "geheime link" is geen toegangscontrole.
--
-- Eerst alle bestaande policies op deze twee tabellen weghalen, zodat we niet
-- afhangen van hun namen, dan één leespolicy voor anon en authenticated.

do $$
declare p record;
begin
  for p in
    select tablename, policyname from pg_policies
    where schemaname = 'public' and tablename in ('crawls', 'bevindingen')
  loop
    execute format('drop policy %I on public.%I', p.policyname, p.tablename);
  end loop;
end $$;

alter table public.crawls enable row level security;
alter table public.bevindingen enable row level security;

create policy "lezen voor iedereen" on public.crawls
  for select to anon, authenticated using (true);
create policy "lezen voor iedereen" on public.bevindingen
  for select to anon, authenticated using (true);

-- De allowlist (toegestane_gebruikers) en is_toegestaan() blijven staan maar
-- worden niet meer gebruikt. Opruimen kan later, als dit besluit stand houdt.
