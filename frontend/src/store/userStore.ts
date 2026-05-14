import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface UserProfile {
  id: number
  name: string
  exam_target: string
  exam_category: string  // "banking" | "ug_entrance"
}

interface UserState {
  user: UserProfile | null
  setUser: (user: UserProfile) => void
  logout: () => void
}

export const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      user: null,
      setUser: (user) => set({ user }),
      logout: () => set({ user: null }),
    }),
    {
      name: 'adaptive-test-user',   // localStorage key
      partialize: (state) => ({ user: state.user }),  // only persist user, not functions
    },
  ),
)
