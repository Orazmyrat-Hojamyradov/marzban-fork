export type AdminType = {
  username: string;
  is_sudo: boolean;
  telegram_id: number | null;
  discord_webhook: string | null;
  users_usage: number;
  user_limit: number | null;
  traffic_limit: number | null;
  user_count: number;
};

export type AdminCreate = {
  username: string;
  password: string;
  is_sudo: boolean;
  user_limit: number | null;
  traffic_limit: number | null;
  telegram_id: number | null;
  discord_webhook: string | null;
};

export type AdminModify = {
  password?: string;
  is_sudo: boolean;
  user_limit: number | null;
  traffic_limit: number | null;
  telegram_id: number | null;
  discord_webhook: string | null;
};
