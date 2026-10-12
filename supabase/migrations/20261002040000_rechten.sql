-- Rechten op tabelniveau, naast de RLS-policies.
--
-- Een policy alleen is niet genoeg: de rol heeft ook het recht op de tabel nodig.
-- De migratie van stap 1 (20261002000000_open_lezen.sql) zette alleen policies, dus
-- `anon` kreeg "permission denied for table crawls". Dit is al toegepast in Supabase.

-- Lezen voor iedereen, ook zonder sessie.
grant select on public.crawls, public.bevindingen to anon;

-- De twee nieuwe tabellen kregen standaard alle rechten voor anon en authenticated.
-- RLS blokkeert schrijven al (er is geen schrijfpolicy), maar de rechten hoeven er
-- niet te zijn: alleen de service-role key schrijft.
revoke insert, update, delete, truncate, references, trigger
  on public.goedgekeurd, public.crawl_aanvragen from anon, authenticated;
