create table share_tokens (
  id               uuid primary key default gen_random_uuid(),
  client_id        uuid not null references clients(id) on delete cascade,
  token            uuid not null default gen_random_uuid() unique,
  expires_at       timestamptz not null,
  created_by_rm_id uuid not null references rms(id),
  created_at       timestamptz not null default now()
);
create index share_tokens_token_idx on share_tokens(token);
create index share_tokens_client_idx on share_tokens(client_id);
