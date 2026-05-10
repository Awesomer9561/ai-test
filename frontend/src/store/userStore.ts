import { create } from 'zustand'

export interface UserProfile {
  id: number
  name: string
  exam_target: string
}

interface UserState {
  user: UserProfile | null
  setUser: (user: UserProfile) => void
  logout: () => void
}

export const useUserStore = create<UserState>((set) => ({
  user: null,
  setUser: (user) => set({ user }),
  logout: () => set({ user: null }),
}))
