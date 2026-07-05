import {Form, Input, message, Modal} from 'antd';
import {useMutation} from '@tanstack/react-query';
import {apiMutate} from '../lib/apiMutate';

interface MyCredentialsFormValues {
  login: string | null;
  password: string | null;
}

export function MyAccountModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [form] = Form.useForm<MyCredentialsFormValues>();

  const saveMutation = useMutation({
    mutationFn: (values: MyCredentialsFormValues) =>
      apiMutate('/api/me', 'PUT', { login: values.login || null, password: values.password || null }),
    onSuccess: () => {
      message.success('Сохранено');
      form.resetFields();
      onClose();
    },
    onError: (e: Error) => message.error(e.message),
  });

  return (
    <Modal
      title="Мои учётные данные"
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      okText="Сохранить"
      confirmLoading={saveMutation.isPending}
    >
      <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate(v)}>
        <Form.Item name="login" label="Логин (оставьте пустым, чтобы не менять)">
          <Input placeholder="Логин для входа" />
        </Form.Item>
        <Form.Item name="password" label="Пароль (оставьте пустым, чтобы не менять)">
          <Input.Password placeholder="Новый пароль" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
