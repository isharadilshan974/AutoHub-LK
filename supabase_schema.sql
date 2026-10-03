-- AutoHub LK Business Edition - Supabase schema
-- Run this whole file in Supabase SQL Editor.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  full_name text,
  phone text,
  city text,
  bio text,
  role text not null default 'buyer' check (role in ('buyer','seller','dealer','admin')),
  is_verified boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.vehicles (
  id uuid primary key default gen_random_uuid(),
  seller_id uuid not null references public.profiles(id) on delete cascade,
  title text not null,
  category text not null,
  make text not null,
  model text not null,
  year integer,
  price numeric(14,2) not null default 0,
  mileage integer not null default 0,
  condition text,
  fuel_type text,
  transmission text,
  location text,
  description text,
  images text[] not null default '{}',
  status text not null default 'pending' check (status in ('pending','approved','rejected','sold','draft')),
  is_featured boolean not null default false,
  views integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.favourites (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  vehicle_id uuid not null references public.vehicles(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique(user_id, vehicle_id)
);

create table if not exists public.enquiries (
  id uuid primary key default gen_random_uuid(),
  vehicle_id uuid not null references public.vehicles(id) on delete cascade,
  buyer_id uuid not null references public.profiles(id) on delete cascade,
  message text not null,
  status text not null default 'new' check (status in ('new','read','contacted','closed')),
  created_at timestamptz not null default now()
);

create index if not exists vehicles_status_idx on public.vehicles(status);
create index if not exists vehicles_category_idx on public.vehicles(category);
create index if not exists vehicles_location_idx on public.vehicles(location);
create index if not exists vehicles_price_idx on public.vehicles(price);
create index if not exists vehicles_seller_idx on public.vehicles(seller_id);
create index if not exists enquiries_buyer_idx on public.enquiries(buyer_id);
create index if not exists enquiries_vehicle_idx on public.enquiries(vehicle_id);

-- New users automatically receive a profile.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email, full_name, phone, city, role)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name',''),
    coalesce(new.raw_user_meta_data->>'phone',''),
    coalesce(new.raw_user_meta_data->>'city',''),
    case when (new.raw_user_meta_data->>'role') in ('seller','dealer') then new.raw_user_meta_data->>'role' else 'buyer' end
  )
  on conflict (id) do update set email = excluded.email;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists(select 1 from public.profiles where id = auth.uid() and role = 'admin');
$$;

grant execute on function public.is_admin() to anon, authenticated;

alter table public.profiles enable row level security;
alter table public.vehicles enable row level security;
alter table public.favourites enable row level security;
alter table public.enquiries enable row level security;

-- Profiles
 drop policy if exists "profiles_select_public" on public.profiles;
create policy "profiles_select_public" on public.profiles for select using (true);
drop policy if exists "profiles_update_self" on public.profiles;
create policy "profiles_update_self" on public.profiles for update using (auth.uid() = id) with check (auth.uid() = id);

-- Vehicles: public may read approved listings; sellers manage their own listings; admins manage all.
drop policy if exists "vehicles_public_read_approved" on public.vehicles;
create policy "vehicles_public_read_approved" on public.vehicles for select using (status = 'approved' or seller_id = auth.uid() or public.is_admin());
drop policy if exists "vehicles_insert_owner" on public.vehicles;
create policy "vehicles_insert_owner" on public.vehicles for insert to authenticated with check (seller_id = auth.uid());
drop policy if exists "vehicles_update_owner_or_admin" on public.vehicles;
create policy "vehicles_update_owner_or_admin" on public.vehicles for update to authenticated using (seller_id = auth.uid() or public.is_admin()) with check (seller_id = auth.uid() or public.is_admin());
drop policy if exists "vehicles_delete_owner_or_admin" on public.vehicles;
create policy "vehicles_delete_owner_or_admin" on public.vehicles for delete to authenticated using (seller_id = auth.uid() or public.is_admin());

-- Favourites
drop policy if exists "favourites_self_select" on public.favourites;
create policy "favourites_self_select" on public.favourites for select to authenticated using (user_id = auth.uid());
drop policy if exists "favourites_self_insert" on public.favourites;
create policy "favourites_self_insert" on public.favourites for insert to authenticated with check (user_id = auth.uid());
drop policy if exists "favourites_self_delete" on public.favourites;
create policy "favourites_self_delete" on public.favourites for delete to authenticated using (user_id = auth.uid());

-- Enquiries: buyer can create/read own; vehicle owner can read/update; admin can read/update.
drop policy if exists "enquiries_buyer_insert" on public.enquiries;
create policy "enquiries_buyer_insert" on public.enquiries for insert to authenticated with check (buyer_id = auth.uid());
drop policy if exists "enquiries_participants_select" on public.enquiries;
create policy "enquiries_participants_select" on public.enquiries for select to authenticated using (
  buyer_id = auth.uid() or exists(select 1 from public.vehicles v where v.id = vehicle_id and v.seller_id = auth.uid()) or public.is_admin()
);
drop policy if exists "enquiries_participants_update" on public.enquiries;
create policy "enquiries_participants_update" on public.enquiries for update to authenticated using (
  buyer_id = auth.uid() or exists(select 1 from public.vehicles v where v.id = vehicle_id and v.seller_id = auth.uid()) or public.is_admin()
) with check (
  buyer_id = auth.uid() or exists(select 1 from public.vehicles v where v.id = vehicle_id and v.seller_id = auth.uid()) or public.is_admin()
);

-- Storage bucket for vehicle photos.
insert into storage.buckets (id, name, public)
values ('vehicle-images', 'vehicle-images', true)
on conflict (id) do update set public = true;

alter table storage.objects enable row level security;
drop policy if exists "vehicle_images_public_read" on storage.objects;
create policy "vehicle_images_public_read" on storage.objects for select using (bucket_id = 'vehicle-images');
drop policy if exists "vehicle_images_auth_insert" on storage.objects;
create policy "vehicle_images_auth_insert" on storage.objects for insert to authenticated with check (bucket_id = 'vehicle-images');
drop policy if exists "vehicle_images_owner_update" on storage.objects;
create policy "vehicle_images_owner_update" on storage.objects for update to authenticated using (bucket_id = 'vehicle-images' and owner_id = auth.uid()::text);
drop policy if exists "vehicle_images_owner_delete" on storage.objects;
create policy "vehicle_images_owner_delete" on storage.objects for delete to authenticated using (bucket_id = 'vehicle-images' and owner_id = auth.uid()::text);

-- Create the first admin manually after registering your account:
-- update public.profiles set role='admin' where email='YOUR_EMAIL@example.com';

