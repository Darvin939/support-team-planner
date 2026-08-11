import {Form, Select} from 'antd';
import {ASSIGNMENT_STATUS_OPTIONS} from '../../domain/types';


export function AssignmentStatusField({disabled}: {disabled: boolean}) {
  return (
    <Form.Item name="status" label="Статус">
      <Select aria-label="Статус" disabled={disabled} options={ASSIGNMENT_STATUS_OPTIONS}/>
    </Form.Item>
  );
}
