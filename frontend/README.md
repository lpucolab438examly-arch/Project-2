# FraudNet.AI Frontend

Modern Next.js frontend application for the FraudNet.AI fraud detection platform.

## 🚀 Features

- **Next.js 14**: Latest App Router with server components
- **TypeScript**: Type-safe development with comprehensive interfaces
- **Tailwind CSS**: Modern, responsive styling with custom fraud detection theme
- **Authentication**: JWT-based auth with role-based access control (RBAC)
- **Real-time**: Live dashboard with real-time fraud detection metrics
- **Charts**: Interactive data visualization with Recharts
- **Responsive**: Mobile-first design with responsive navigation

## 📋 Prerequisites

- Node.js 18+ and npm
- Backend API server running (see `/backend` directory)

## 🛠 Installation

1. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Environment configuration:**
   Create `.env.local`:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:5000/api
   NEXT_PUBLIC_WS_URL=ws://localhost:5000
   NODE_ENV=development
   ```

3. **Start development server:**
   ```bash
   npm run dev
   ```

4. **Open application:**
   Navigate to [http://localhost:3000](http://localhost:3000)

## 🔧 Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint
- `npm run type-check` - TypeScript type checking

## 📁 Project Structure

```
src/
├── app/                    # Next.js App Router pages
│   ├── dashboard/          # Protected dashboard pages
│   ├── login/             # Authentication pages
│   ├── layout.tsx         # Root layout with providers
│   ├── page.tsx           # Home page (redirect logic)
│   └── globals.css        # Global styles and theme
├── components/            # Reusable React components
│   └── DashboardLayout.tsx # Main dashboard layout
├── hooks/                 # Custom React hooks
│   └── useAuth.tsx        # Authentication hook and providers
├── lib/                   # Utility libraries
│   ├── api-client.ts      # API client with JWT handling
│   └── utils.ts           # Helper functions
└── types/                 # TypeScript type definitions
    └── index.ts           # All interface definitions
```

## 🔐 Authentication

### Default Demo Credentials
- **Admin:** admin@fraudnet.ai / admin123
- **Analyst:** analyst@fraudnet.ai / analyst123  
- **Viewer:** viewer@fraudnet.ai / viewer123

### Role-Based Access Control
- **Admin**: Full system access, user management, settings
- **Analyst**: Transaction analysis, model management
- **Viewer**: Read-only dashboard access

## 🎨 Theming

Custom Tailwind theme with fraud detection specific colors:

```css
--primary: Blue (#3b82f6) - Primary actions, navigation
--success: Green (#10b981) - Safe transactions, positive metrics  
--warning: Orange (#f59e0b) - Medium risk, warnings
--danger: Red (#ef4444) - Fraud alerts, high risk, errors
--info: Blue variant - Information, model stats
```

## 📱 Pages & Features

### Dashboard (`/dashboard`)
- **Overview**: Real-time metrics, fraud trend charts, system health
- **Transactions**: Searchable transaction list with risk scoring
- **Models**: ML model management and performance metrics
- **Analytics**: Deep dive fraud analysis and reporting
- **Settings**: System configuration (admin only)

### Components
- **Authentication**: Login form with validation, protected routes
- **Navigation**: Responsive sidebar with role-based menu items
- **Charts**: Interactive fraud trend and risk distribution charts
- **Tables**: Sortable, filterable transaction tables with pagination

## 🔌 API Integration

TypeScript API client with:
- JWT token management and automatic refresh
- Request/response interceptors for auth headers
- Error handling with user-friendly messages
- Type-safe method signatures matching backend endpoints

```typescript
// Example API usage
const transactions = await apiClient.getTransactions()
const metrics = await apiClient.getDashboardMetrics()
await apiClient.predictTransaction(transactionData)
```

## 📊 Data Visualization

Recharts integration for:
- **Line Charts**: Fraud detection trends over time
- **Area Charts**: Transaction volume and risk distribution  
- **Pie Charts**: Risk score categorization
- **Bar Charts**: Model performance metrics

## 🛡 Security Features

- Client-side input validation with Zod schemas
- JWT token storage in secure httpOnly cookies (when deployed)
- CSRF protection with request headers
- Role-based route protection at component level
- XSS protection with Content Security Policy headers

## 🚀 Deployment

### Production Build
```bash
npm run build
npm run start
```

### Docker Container
```bash
docker build -t fraudnet-frontend .
docker run -p 3000:3000 fraudnet-frontend
```

### Environment Variables
```env
NEXT_PUBLIC_API_URL=https://api.fraudnet.ai/api
NEXT_PUBLIC_WS_URL=wss://api.fraudnet.ai
NODE_ENV=production
```

## 🔗 Backend Integration

Frontend connects to Flask backend APIs:
- Authentication: `/auth/login`, `/auth/logout`, `/auth/refresh`
- Transactions: `/transactions`, `/transactions/predict`
- Models: `/models`, `/models/train`, `/models/evaluate`
- Dashboard: `/dashboard/metrics`, `/dashboard/health`

## 🧪 Development

### Code Quality
- TypeScript strict mode enabled
- ESLint configuration with Next.js and TypeScript rules
- Prettier for consistent code formatting
- Husky git hooks for pre-commit validation

### Component Development
- React functional components with hooks
- Custom hooks for state and API management  
- Error boundaries for graceful error handling
- Loading states and skeleton screens

## 🐛 Troubleshooting

### Common Issues

**CORS errors:** Ensure backend CORS is configured for frontend URL
**Token expiry:** Check JWT token refresh logic in API client
**Build errors:** Verify all TypeScript interfaces match API responses
**Styling issues:** Check Tailwind CSS configuration and custom theme variables

### Debug Mode
```bash
NODE_ENV=development npm run dev
```

## 📈 Performance

- Next.js optimizations: image optimization, code splitting, static generation
- Client-side caching with React Query (planned)
- Lazy loading for heavy components
- Bundle analysis: `npm run build-stats`

## 🤝 Contributing

1. Follow TypeScript strict mode conventions
2. Add proper JSDoc comments for complex functions
3. Write responsive CSS with Tailwind utilities
4. Test authentication flows with all user roles
5. Validate forms with Zod schemas

## 📄 License

Part of the FraudNet.AI project - see main project license.