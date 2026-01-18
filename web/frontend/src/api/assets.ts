import client from './client';

export interface AssetResponse {
  id: string;
  filename: string;
  url: string;
}

export const assetsApi = {
  upload: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return client.post<AssetResponse>('/assets/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
};
