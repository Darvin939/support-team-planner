import {Form, Input, message, Modal} from 'antd';
import {useMutation} from '@tanstack/react-query';
import {apiMutate} from '../lib/apiMutate';

interface MyPasswordFormValues {
  password: string | null;
}

export function MyAccountModal({open, onClose}: { open: boolean; onClose: () => void }) {
  const [form] = Form.useForm<MyPasswordFormValues>();

  const saveMutation = useMutation({
    mutationFn: (values: MyPasswordFormValues) =>
      apiMutate('/api/me', 'PUT', {password: values.password || null}),
    onSuccess: () => {
      message.success('Сохранено');
      form.resetFields();
      onClose();
    },
    onError: (e: Error) => message.error(e.message),
  });

  return (
    <Modal
      title="Смена пароля"
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      okText="Сохранить"
      confirmLoading={saveMutation.isPending}
    >
      <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate(v)}>
        <Form.Item name="password" label="Пароль (оставьте пустым, чтобы не менять)">
          <Input.Password placeholder="Новый пароль"/>
        </Form.Item>
      </Form>
    </Modal>
  );
}
