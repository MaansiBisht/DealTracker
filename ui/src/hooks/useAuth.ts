import { useCallback, useEffect, useState } from 'react';
import { ApiError, api } from '~/lib/api';
import type { AuthMeResponse, User } from '~/types/job';

interface AuthState {
  user: User | null;
  telegramBotConfigured: boolean;
  telegramBotUsername: string | null;
  loading: boolean;
  // Distinguishes "still booting" from "definitely signed out", so the
  // sign-in screen doesn't flash for the authenticated mount.
  bootstrapped: boolean;
}

const INITIAL: AuthState = {
  user: null,
  telegramBotConfigured: false,
  telegramBotUsername: null,
  loading: true,
  bootstrapped: false,
};

export function useAuth() {
  const [state, setState] = useState<AuthState>(INITIAL);

  const fetchMe = useCallback(async () => {
    try {
      const me: AuthMeResponse = await api.authMe();
      setState({
        user: me.user,
        telegramBotConfigured: me.telegram_bot_configured,
        telegramBotUsername: me.telegram_bot_username,
        loading: false,
        bootstrapped: true,
      });
    } catch (err) {
      // 401 is the expected "not signed in" path — treat any error as
      // signed-out, surface unexpected problems via console for debugging.
      if (!(err instanceof ApiError) || err.status !== 401) {
        // eslint-disable-next-line no-console
        console.error('auth/me failed', err);
      }
      setState({
        user: null,
        telegramBotConfigured: false,
        telegramBotUsername: null,
        loading: false,
        bootstrapped: true,
      });
    }
  }, []);

  useEffect(() => {
    void fetchMe();
  }, [fetchMe]);

  const logout = useCallback(async () => {
    try {
      await api.authLogout();
    } finally {
      setState({
        user: null,
        telegramBotConfigured: false,
        telegramBotUsername: null,
        loading: false,
        bootstrapped: true,
      });
    }
  }, []);

  return {
    ...state,
    refresh: fetchMe,
    logout,
  };
}
