import type {Task} from './task-engine';

export type TaskFocusTarget='field'|'review'|'action';

export function taskFocusTarget(task:Pick<Task,'status'>|null,field:string|null|undefined):TaskFocusTarget|null{
 if(!task)return null;
 if(task.status==='collecting')return field?'field':null;
 if(task.status==='review')return 'review';
 return 'action';
}
