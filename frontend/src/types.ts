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

export interface PortfolioInput {
  name: string;
  owner: string;
  description: string;
  productArea: string;
  status: 'Active' | 'Archived';
}

export interface Portfolio extends PortfolioInput {
  id: string;
  applicationCount: number;
  qualityScore: number | null;
}

export interface ApplicationSummary {
  id: string;
  name: string;
  portfolioId: string;
  qualityScore: number | null;
  riskLevel: string | null;
}

export interface Page<T> { items: T[]; total: number; limit: number; offset: number }
