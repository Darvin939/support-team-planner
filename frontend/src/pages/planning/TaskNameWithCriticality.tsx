import type {Criticality} from '../../domain/types';
import {CriticalityBadge} from '../../components/planningBadges';

export function TaskNameWithCriticality({name, criticality}: {name: string; criticality: Criticality}) {
  return (
    <div data-task-row-name style={{fontWeight: 500, overflowWrap: 'anywhere'}}>
      <span
        data-task-row-criticality
        style={{display: 'inline-block', marginRight: 6, verticalAlign: 'baseline', whiteSpace: 'nowrap'}}
      >
        <CriticalityBadge value={criticality}/>
      </span>
      {name}
    </div>
  );
}
