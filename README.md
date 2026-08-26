# Daykin Backend — Django REST API

## Quick Start

```bash
pip install -r requirements.txt
python manage.py migrate
python seed.py              # loads sample celebrities, articles, charities, love stories
python manage.py runserver
```

## URLs

| URL | What you get |
|-----|-------------|
| http://localhost:8000/admin/ | Django Admin panel |
| http://localhost:8000/api/docs/ | **Swagger UI** (interactive) |
| http://localhost:8000/api/redoc/ | ReDoc (clean docs) |
| http://localhost:8000/api/schema/ | Raw OpenAPI JSON/YAML |

**Admin credentials:** `admin` / `admin123`

---

## API Endpoints

### Auth
| Method | URL | Access |
|--------|-----|--------|
| POST | /api/auth/register/ | Public |
| POST | /api/auth/login/ | Public — returns JWT tokens |
| POST | /api/auth/refresh/ | Public |
| GET/PUT | /api/auth/me/ | Authenticated |

### Celebrities *(Admin: write)*
| Method | URL | Access |
|--------|-----|--------|
| GET | /api/celebrities/ | Public |
| POST | /api/celebrities/ | **Admin only** |
| GET | /api/celebrities/{id}/ | Public |
| PUT/PATCH | /api/celebrities/{id}/ | **Admin only** |
| DELETE | /api/celebrities/{id}/ | **Admin only** |
| GET | /api/celebrities/birthdays-today/ | Public |

### Articles *(Admin: write)*
| Method | URL | Access |
|--------|-----|--------|
| GET | /api/articles/ | Public |
| POST | /api/articles/ | **Admin only** |
| POST | /api/articles/{id}/like/ | Authenticated |

### Posts *(any logged-in user)*
| GET/POST | /api/posts/ | Read: Public · Write: Auth |
| POST | /api/posts/{id}/like/ | Authenticated |

### Charities *(Admin: write)*
| GET | /api/charities/ | Public |
| POST | /api/charities/ | **Admin only** |

### Love Stories *(any logged-in user)*
| GET/POST | /api/love-stories/ | Read: Public · Write: Auth |
| POST | /api/love-stories/{id}/like/ | Authenticated |

---

## Filtering & Search
```
GET /api/celebrities/?search=ronaldo
GET /api/articles/?category=sports
GET /api/articles/?search=champions
GET /api/charities/?tag=Health
```

## Authentication
All write requests need a JWT `Authorization` header:
```
Authorization: Bearer <access_token>
```
Get the token from `POST /api/auth/login/`.
