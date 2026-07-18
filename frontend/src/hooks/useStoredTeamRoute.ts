import {useEffect} from 'react';
import {useNavigate} from 'react-router-dom';
import type {Team} from './useTeams';

const STORAGE_TEAM_ID = 'selectedTeamId';

export function useStoredTeamRoute(basePath: string, teamId: number | undefined, teams: Team[] | undefined) {
  const navigate = useNavigate();

  useEffect(() => {
    if (!teams) return;
    if (teamId !== undefined) {
      if (!teams.some((team) => team.id === teamId)) {
        localStorage.removeItem(STORAGE_TEAM_ID);
        navigate(basePath, {replace: true});
      }
      return;
    }

    const saved = localStorage.getItem(STORAGE_TEAM_ID);
    if (saved && teams.some((team) => team.id === Number(saved))) {
      navigate(`${basePath}/${saved}`, {replace: true});
    } else if (saved) {
      localStorage.removeItem(STORAGE_TEAM_ID);
    }
  }, [basePath, navigate, teamId, teams]);

  return (value: number | undefined) => {
    if (value === undefined) localStorage.removeItem(STORAGE_TEAM_ID);
    else localStorage.setItem(STORAGE_TEAM_ID, String(value));
    navigate(value === undefined ? basePath : `${basePath}/${value}`);
  };
}
