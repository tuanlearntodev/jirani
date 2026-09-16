# OFFLIB Frontend - Setup Guide

## 📦 Project Overview

OFFLIB is an offline library solution for interactive learning. This is a **complete architectural redesign** from the legacy codebase, implementing the OFFLIB specification with role-based access control, modular components, and a scalable structure.

### Key Changes on `main` Branch
- ✅ **New folder structure** following atomic design principles (atoms, molecules, organisms, templates)
- ✅ **React Router DOM** for client-side routing with protected routes
- ✅ **AuthContext + useAuth hook** for global auth state and role-based access
- ✅ **Tailwind CSS** + PostCSS for modern, utility-first styling
- ✅ **P0 (core) features** fully scaffolded: Login, Signup, LibraryHome, Viewers, Teacher Dashboard
- ✅ **P2/P3 (future) placeholders** ready for implementation
- ✅ **Production-ready build** (npm run build succeeds ✓)

> **Legacy Code**: All original files have been preserved in the `legacy` branch. Start fresh development on `main`.

---

## 🚀 Getting Started

### Prerequisites
- **Node.js** 16+ (recommended: 18+)
- **npm** 8+
- Git (for cloning and branch management)

### Installation

```bash
cd jirani-frontend
npm install
npm run dev
```

App will run on `http://localhost:5173` by default.

---

## 📁 Project Structure

```
src/
├── assets/                # Static images, fonts, etc.
├── components/
│   ├── atoms/            # Basic UI blocks (Button, Input, Icon, Avatar)
│   ├── molecules/        # Composed components (FormField, SearchBar, MediaCard)
│   ├── organisms/        # Complex components (LoginForm, DataTable, VideoPlayer, BookViewer)
│   ├── templates/        # Page layouts (AuthLayout, StudentLayout, TeacherLayout)
│   ├── ProtectedRoute.jsx   # Role-based access guard
│
├── pages/
│   ├── auth/             # LoginPage, SignupPage, OnboardingPage, LandingPage
│   ├── student/          # LibraryHome, BookViewerPage, VideoViewerPage, History, etc.
│   ├── teacher/          # TeacherDashboard, MediaManagement, UserManagement, Analytics
│   └── AccountInfo.jsx   # Shared across roles
│
├── hooks/
│   └── useAuth.js        # Custom hook for auth context (easier than useContext)
│
├── context/
│   └── AuthContext.jsx   # Global auth state (isAuthenticated, user, role, login/logout)
│
├── services/
│   └── api/
│       ├── authApi.js    # Login, signup, password reset (TODO: wire to backend)
│       ├── mediaApi.js   # Fetch/upload media, search, get stats
│       └── userApi.js    # Manage students, reset passwords
│
├── utils/
│   └── formatters.js     # Helper functions (formatDate, formatDuration, truncateText)
│
├── styles/
│   └── jirani_style.scss # Legacy Bootstrap imports (can migrate to Tailwind)
│
├── App.jsx              # Main router with all routes and AuthProvider
├── main.jsx             # Entry point with BrowserRouter
└── index.css            # Global styles + Tailwind directives

```

---

## 🔐 Authentication & Role-Based Access

### User Roles
- **Student**: Access `/student/*` routes (library, viewers, history)
- **Teacher**: Access `/teacher/*` routes (dashboard, media management, user management)
- **Anonymous**: Redirect to `/auth/login`

### AuthContext API
```javascript
const { 
  isAuthenticated,  // bool
  user,            // { email, id, fullName }
  role,            // 'student' | 'teacher' | 'admin' | null
  login,           // (userData, userRole) => void
  logout,          // () => void
} = useAuth()
```

### Protected Route Usage
```javascript
<Route
  path="/student/library"
  element={<ProtectedRoute component={LibraryHome} requiredRole="student" />}
/>

<Route
  path="/teacher/dashboard"
  element={<ProtectedRoute component={TeacherDashboard} requiredRole="teacher" />}
/>
```

**Behavior**:
- Not logged in → Redirect to `/auth/login`
- Logged in but wrong role → Redirect to role-specific home page
- Correct role → Render component

---

## 📋 Implemented Features (P0 - Core)

### ✅ Auth Pages
- **LoginPage**: Email + password login with role selection
- **SignupPage**: New user registration
- **AccountInfo**: User profile, password change, logout

### ✅ Student Pages
- **LibraryHome**: Recommended + continue reading/watching sections with search bar
- **BookViewerPage**: PDF/EPUB viewer (TODO: integrate react-pdf or react-epub-viewer)
- **VideoViewerPage**: HTML5 video player (TODO: integrate react-player)

### ✅ Teacher Pages
- **TeacherDashboard**: Library statistics and quick action links
- **MediaManagement**: Upload media and table to edit/delete
- **UserManagement**: Add students and reset passwords

### ✅ Shared Components
- **AuthLayout**: Centered form layout for auth pages
- **StudentLayout**: Header + main + footer for student pages
- **TeacherLayout**: Admin-style layout with sidebar navigation
- **DataTable**: Reusable table organism for media/user management
- **ProtectedRoute**: Role-based access guard

---

## 📋 Planned Features (P2/P3 - Future)

### P2 - Semi Low Priority
- **SearchAndFilterPage**: Advanced filters (type, subject, date range)
- **ItemDetailPage**: Metadata + details before opening media
- **HistoryPage**: Reading/watch history + "watch later"
- **OnboardingPage**: Interest selection + avatar setup for new students
- **AnalyticsPage**: Per-student engagement metrics (teacher view)
- **ThemeContext**: Dark mode toggle

### P3 - Low Priority
- **LandingPage**: Informational homepage

---

## 🛠 Available Scripts

```bash
# Install dependencies
npm install

# Start dev server (http://localhost:5173)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint code
npm lint
```

---

## 🔗 API Integration (TODO)

All API calls are stubbed in `/src/services/api/`. Replace `// TODO` comments with real backend calls:

### authApi.js
- `login(email, password)` → POST /api/auth/login
- `signup(fullName, email, password, role)` → POST /api/auth/signup
- `resetPassword(email)` → POST /api/auth/reset-password
- `logout()` → POST /api/auth/logout

### mediaApi.js
- `getRecommendedMedia(studentId)` → GET /api/media/recommended
- `searchMedia(query, filters)` → GET /api/media/search
- `uploadMedia(formData)` → POST /api/media/upload
- `getLibraryStats()` → GET /api/media/stats

### userApi.js
- `getStudents()` → GET /api/users/students
- `addStudent(fullName, email)` → POST /api/users/add-student
- `resetPassword(studentId, email)` → POST /api/users/reset-password

Set backend URL in `.env`:
```
VITE_API_URL=http://localhost:3000
```

---

## 🎨 Styling

- **Tailwind CSS** for utility-first styling (primary)
- **Legacy SCSS** from Bootstrap (in `src/styles/jirani_style.scss`) for gradual migration
- **PostCSS** for autoprefixing

Tailwind is configured in `tailwind.config.js` and imported in `index.css`.

---

## 📚 Key Design Decisions

1. **Atomic Design**: Scales from atoms (Button) → molecules (FormField) → organisms (LoginForm) → templates/pages
2. **Context API for Auth**: Simple, no Redux needed for auth state
3. **Protected Routes**: Centralized access control in React Router
4. **Modular Services**: API logic separated from components
5. **Utility Functions**: Formatters in `/utils` for reusability

---

## ⚠️ Important Notes

- **Mock Auth**: LoginPage currently mocks successful login. Wire to `authApi.login()` before production.
- **Bootstrap Warnings**: SCSS deprecation warnings are from Bootstrap 5 (harmless, will be fixed in Bootstrap 6).
- **localStorage**: Auth state is persisted to localStorage for session continuity (optional, can disable).

---

## 🤝 Contributing

When adding new features:
1. Follow the folder structure (atoms → molecules → organisms → pages)
2. Use `useAuth()` for accessing auth state
3. Wrap protected pages with `<ProtectedRoute>`
4. Keep API calls in `/services/api/`
5. Use Tailwind classes for styling

---

## 📖 User Stories (Reference)

### User Story 1: Student Access Control
A student tries to access `/teacher/dashboard` directly:
1. ProtectedRoute checks `isAuthenticated` (✓) and `role` ('student')
2. Role doesn't match required role ('teacher')
3. Redirected to `/student/library`

### User Story 2: Unauthenticated Access
An unauthenticated user tries to access `/student/library`:
1. ProtectedRoute checks `isAuthenticated` (✗)
2. Redirected to `/auth/login`
3. (Optional) After login, auto-redirect to original intended destination

---

## 📞 Support

For issues or questions:
1. Check the `/legacy` branch for original code
2. Review the folder structure and examples in `/src/pages/`
3. Inspect `useAuth()` hook usage for auth patterns
4. Verify `ProtectedRoute` implementation for access control

---

**Happy coding! 🚀 The foundation is ready—focus on features, not architecture.**
