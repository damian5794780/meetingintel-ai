import type { components } from './api-schema';

type Schemas = components['schemas'];

export type Briefing = Schemas['Briefing'];
export type Claim = Schemas['Claim'];
export type Source = Schemas['Source'];
export type Health = Schemas['HealthResponse'];
export type JobStatus = Schemas['ResearchStatus'];
export type ResearchResult = NonNullable<Schemas['ResearchJob']['result']>;
export type ResearchRequest = Schemas['ResearchRequest'];
export type ResearchTicket = Schemas['ResearchTicket'];
export type Ticket = Pick<ResearchTicket, 'id' | 'access_token'>;
