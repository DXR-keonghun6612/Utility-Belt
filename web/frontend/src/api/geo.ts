import client from './client';

export interface LocationResponse {
  id: string;
  latitude: number;
  longitude: number;
  address?: string;
}

export const geoApi = {
  create: (latitude: number, longitude: number, address?: string) => 
    client.post<LocationResponse>('/geo', { latitude, longitude, address }),
};
