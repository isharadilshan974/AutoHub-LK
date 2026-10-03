# AutoHub LK — Business Edition V4

Sri Lankan vehicle marketplace built with Python + Streamlit + Supabase.

## Stack
- Python
- Streamlit
- Supabase Auth
- Supabase PostgreSQL
- Supabase Storage
- Streamlit Community Cloud

## V4 features
- Real email/password authentication
- Buyer / Seller / Dealer / Admin roles
- Persistent PostgreSQL vehicle listings
- Seller vehicle posting with up to 8 photos
- Admin approval workflow
- Public approved listings
- Search + category + condition + location + price filters
- Vehicle detail pages
- Seller profile information
- WhatsApp + phone contact links
- Facebook share links
- Favourites
- Buyer enquiries
- Seller/admin message inbox foundation
- Finance estimate calculator
- Admin dashboard
- Streamlit secrets support
- Row Level Security policies

## 1. Supabase setup
Create a Supabase project. Open **SQL Editor** and run `supabase_schema.sql` completely.

Then register one account in AutoHub LK and run this SQL once to make that account admin:

```sql
update public.profiles
set role='admin'
where email='YOUR_EMAIL@example.com';
```

## 2. Streamlit secrets
In Streamlit Community Cloud → your app → Manage app → Settings → Secrets, add:

```toml
SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
SUPABASE_KEY = "YOUR-PUBLISHABLE-OR-ANON-KEY"
```

Never commit service-role keys or passwords to GitHub.

## 3. requirements
Community Cloud reads `requirements.txt` and installs the dependencies.

## 4. Deploy
Repository: `isharadilshan974/AutoHub-LK`
Branch: `main`
Main file: `app.py`

Commit/push the V4 files to GitHub. Streamlit Community Cloud will rebuild the app.

## Important production notes
- Supabase PostgreSQL and Storage are persistent; do not use local SQLite for the public version.
- RLS is required. Do not expose a service-role key to the Streamlit client.
- Facebook/WhatsApp share links are not the same as automatic posting. Official social APIs require the platform's permissions, credentials and policy-compliant workflows.
- For high-volume traffic, a dedicated web backend/frontend may eventually be preferable to Streamlit, but this V4 architecture provides a practical business MVP foundation.
