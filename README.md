# 🚗 AutoHub LK

AutoHub LK is a Sri Lankan vehicle marketplace MVP built with **Python + Streamlit + SQLite**.

## V1 Features

- Home page
- Vehicle search and filters
- Vehicle categories
- Buyer registration
- Seller registration
- Vehicle listing creation
- Vehicle photo upload
- Admin approval workflow
- Seller dashboard
- Buyer favourites
- Buyer enquiries
- WhatsApp contact links
- Finance calculator
- Basic marketplace statistics
- SQLite local database

## Demo Accounts

### Admin
- Email: `admin@autohub.lk`
- Password: `admin1234`

### Seller
- Email: `seller@autohub.lk`
- Password: `seller1234`

## Run Locally

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Using `python -m streamlit` avoids depending on a Windows PATH entry for the `streamlit` executable.

## GitHub

Create a repository named `AutoHub-LK`, then upload:

- `app.py`
- `requirements.txt`
- `.gitignore`
- `README.md`
- `docs/PROJECT_STATUS.md`
- `uploads/.gitkeep`

Do not upload passwords, API keys or `.env` files.

## Streamlit Community Cloud

After pushing to GitHub:

1. Open Streamlit Community Cloud.
2. Sign in with GitHub.
3. Create a new app.
4. Select the `AutoHub-LK` repository.
5. Select the main branch.
6. Set the main file to `app.py`.
7. Deploy.

## Important Production Note

This V1 uses SQLite and local uploads for learning/MVP purposes. Streamlit Community Cloud instances are not a production database or permanent file-storage solution. Before a real public launch, migrate the database to a persistent hosted database and images to persistent object storage.

Real Facebook/TikTok/Instagram/WhatsApp automation is intentionally not faked. Those features require official APIs, authentication, permissions, provider policies and secure secrets.

## Roadmap

### V1
Marketplace foundation.

### V2
- Advanced search
- Dealer/broker accounts
- Better image gallery
- Messaging
- Finance application workflow
- Analytics

### V3
- Persistent cloud database
- Cloud image storage
- Official social integrations
- WhatsApp Business API
- Notifications
- AI features
- Production security
