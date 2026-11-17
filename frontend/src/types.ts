/** The public account returned by the identity API. */
export interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  portfolioAccess: string[];
  status: string;
  defaultLandingPage: 'dashboard' | 'applications';
  permissions: string[];
}

export interface LoginResponse { token: string; user: User }
