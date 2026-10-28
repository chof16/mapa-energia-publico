export const validPeriod = (value: string) => /^20\d{2}T[1-4]$/.test(value);
export const validMarketer = (value: string) => /^R2-\d+$/.test(value) && value !== 'R2-000';
