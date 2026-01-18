import client from './client';

export interface Account {
  code: string;
  name: string;
  category: string;
  side: string;
  description?: string;
}

export interface JournalEntry {
  code: string;
  amount: number;
  description?: string;
}

export interface TransactionCreate {
  date: string;
  description: string;
  debits: JournalEntry[];
  credits: JournalEntry[];
  evidence_id?: string;
  location_id?: string;
}

export interface TransactionUpdate {
  description?: string;
  evidence_id?: string;
  location_id?: string;
}

export interface TransactionResponse {
  id: string;
  date: string;
  description: string;
  debits: any[];
  credits: any[];
  evidence_id?: string;
  location_id?: string;
  is_balanced: boolean;
}

export const accountingApi = {
  // 계정 관련
  getAccounts: () => client.get<Account[]>('/accounts'),
  createAccount: (data: Account) => client.post<Account>('/accounts', data),

  // 거래 관련
  getTransactions: () => client.get<TransactionResponse[]>('/transactions'),
  createTransaction: (data: TransactionCreate) => client.post<TransactionResponse>('/transactions', data),
  updateTransaction: (id: string, data: TransactionUpdate) => client.patch<TransactionResponse>(`/transactions/${id}`, data),
};
