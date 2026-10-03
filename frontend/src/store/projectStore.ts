import { create } from 'zustand';
import type { Project } from '../lib/types';
export type { Project } from '../lib/types';

interface ProjectState {
    currentProject: Project | null;
    projects: Project[];
    setCurrentProject: (project: Project | null) => void;
    setProjects: (projects: Project[]) => void;
    clearState: () => void;
}

export const useProjectStore = create<ProjectState>((set) => ({
    currentProject: null,
    projects: [],
    setCurrentProject: (project) => set({ currentProject: project }),
    setProjects: (projects) => set({ projects }),
    clearState: () => set({ currentProject: null, projects: [] })
}));
