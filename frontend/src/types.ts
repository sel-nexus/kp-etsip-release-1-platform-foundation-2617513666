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

export interface ApplicationInput {
  name: string; description: string; portfolioId: string; productArea: string;
  businessOwner: string; technologyOwner: string; etsOwner: string;
  criticality: 'Low' | 'Medium' | 'High' | 'Critical'; tier: number;
  lifecycleStatus: 'Active' | 'Deprecated' | 'Retired'; technologyStack: string;
  repositoryLink: string | null; pipelineLink: string | null;
  applicationHealthScore: number; qualityScore: number; automationCoverage: number;
  unitTestCoverage: number; openDefects: number; openCriticalDefects: number;
  riskLevel: 'Low' | 'Medium' | 'High';
}
export interface Application extends ApplicationInput { id: string; portfolioName: string; createdAt: string; updatedAt: string }

export interface Page<T> { items: T[]; total: number; limit: number; offset: number }

export interface DashboardPortfolio {
  id: string; name: string; applicationCount: number; qualityScore: number | null; applicationsAtRisk: number;
}
export interface DashboardMetrics {
  enterpriseQualityScore: number | null; applicationHealthScore: number | null; automationMaturityScore: number | null;
  openCriticalDefects: number; applicationsAtRisk: number; totalApplications: number; totalPortfolios: number;
  portfolios: DashboardPortfolio[];
}
