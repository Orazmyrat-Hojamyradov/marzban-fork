import {
  Button,
  FormControl,
  FormErrorMessage,
  FormLabel,
  HStack,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Spinner,
  Switch,
  VStack,
  useToast,
} from "@chakra-ui/react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useAdmins } from "contexts/AdminsContext";
import { FC, useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

const adminSchema = z.object({
  username: z
    .string()
    .min(3, "Username must be at least 3 characters")
    .max(32),
  password: z.string().optional(),
  is_sudo: z.boolean(),
  user_limit: z.union([z.number().int().min(0), z.nan()]).optional().nullable(),
  traffic_limit: z.union([z.number().min(0), z.nan()]).optional().nullable(),
  telegram_id: z.union([z.number().int(), z.nan()]).optional().nullable(),
  discord_webhook: z.string().optional().nullable(),
});

type AdminFormType = z.infer<typeof adminSchema>;

export const AdminDialog: FC = () => {
  const { isCreatingAdmin, editingAdmin, onCreatingAdmin, onEditingAdmin, createAdmin, updateAdmin } = useAdmins();
  const isEditing = !!editingAdmin;
  const isOpen = isCreatingAdmin || isEditing;
  const { t } = useTranslation();
  const toast = useToast();
  const [loading, setLoading] = useState(false);

  const form = useForm<AdminFormType>({
    resolver: zodResolver(adminSchema),
    defaultValues: {
      username: "",
      password: "",
      is_sudo: false,
      user_limit: null,
      traffic_limit: null,
      telegram_id: null,
      discord_webhook: "",
    },
  });

  useEffect(() => {
    if (editingAdmin) {
      form.reset({
        username: editingAdmin.username,
        password: "",
        is_sudo: editingAdmin.is_sudo,
        user_limit: editingAdmin.user_limit,
        traffic_limit: editingAdmin.traffic_limit
          ? editingAdmin.traffic_limit / (1024 * 1024 * 1024)
          : null,
        telegram_id: editingAdmin.telegram_id,
        discord_webhook: editingAdmin.discord_webhook || "",
      });
    } else if (isCreatingAdmin) {
      form.reset({
        username: "",
        password: "",
        is_sudo: false,
        user_limit: null,
        traffic_limit: null,
        telegram_id: null,
        discord_webhook: "",
      });
    }
  }, [editingAdmin, isCreatingAdmin]);

  const onClose = () => {
    onCreatingAdmin(false);
    onEditingAdmin(null);
    form.reset();
  };

  const onSubmit = (values: AdminFormType) => {
    setLoading(true);
    const trafficBytes = values.traffic_limit
      ? Math.round(values.traffic_limit * 1024 * 1024 * 1024)
      : null;

    if (isEditing) {
      updateAdmin(editingAdmin!.username, {
        password: values.password || undefined,
        is_sudo: values.is_sudo,
        user_limit: values.user_limit || null,
        traffic_limit: trafficBytes,
        telegram_id: values.telegram_id || null,
        discord_webhook: values.discord_webhook || null,
      })
        .then(() => {
          toast({
            title: t("admins.adminEdited"),
            status: "success",
            isClosable: true,
            position: "top",
            duration: 3000,
          });
          onClose();
        })
        .catch((err: any) => {
          toast({
            title: err.response?._data?.detail || "Error",
            status: "error",
            isClosable: true,
            position: "top",
            duration: 3000,
          });
        })
        .finally(() => setLoading(false));
    } else {
      if (!values.password) {
        form.setError("password", { message: "Password is required" });
        setLoading(false);
        return;
      }
      createAdmin({
        username: values.username,
        password: values.password,
        is_sudo: values.is_sudo,
        user_limit: values.user_limit || null,
        traffic_limit: trafficBytes,
        telegram_id: values.telegram_id || null,
        discord_webhook: values.discord_webhook || null,
      })
        .then(() => {
          toast({
            title: t("admins.adminCreated"),
            status: "success",
            isClosable: true,
            position: "top",
            duration: 3000,
          });
          onClose();
        })
        .catch((err: any) => {
          toast({
            title: err.response?._data?.detail || "Error",
            status: "error",
            isClosable: true,
            position: "top",
            duration: 3000,
          });
        })
        .finally(() => setLoading(false));
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="md">
      <ModalOverlay bg="blackAlpha.300" backdropFilter="blur(10px)" />
      <ModalContent mx="3">
        <ModalHeader>
          {isEditing ? t("admins.editAdmin") : t("admins.createAdmin")}
        </ModalHeader>
        <ModalCloseButton />
        <form onSubmit={form.handleSubmit(onSubmit)}>
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isInvalid={!!form.formState.errors.username}>
                <FormLabel>{t("admins.username")}</FormLabel>
                <Input
                  {...form.register("username")}
                  isDisabled={isEditing}
                />
                <FormErrorMessage>
                  {form.formState.errors.username?.message}
                </FormErrorMessage>
              </FormControl>

              <FormControl isInvalid={!!form.formState.errors.password}>
                <FormLabel>
                  {t("admins.password")}
                  {isEditing && ` (${t("userDialog.optional")})`}
                </FormLabel>
                <Input type="password" {...form.register("password")} />
                <FormErrorMessage>
                  {form.formState.errors.password?.message}
                </FormErrorMessage>
              </FormControl>

              <FormControl display="flex" alignItems="center">
                <FormLabel mb="0">{t("admins.isSudo")}</FormLabel>
                <Controller
                  name="is_sudo"
                  control={form.control}
                  render={({ field: { onChange, value } }) => (
                    <Switch isChecked={value} onChange={onChange} />
                  )}
                />
              </FormControl>

              <FormControl>
                <FormLabel>{t("admins.userLimit")}</FormLabel>
                <Input
                  type="number"
                  placeholder={t("admins.unlimited")}
                  {...form.register("user_limit", { valueAsNumber: true })}
                  value={form.watch("user_limit") ?? ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    form.setValue(
                      "user_limit",
                      val === "" ? null : parseInt(val)
                    );
                  }}
                />
              </FormControl>

              <FormControl>
                <FormLabel>{t("admins.trafficLimit")} (GB)</FormLabel>
                <Input
                  type="number"
                  step="0.1"
                  placeholder={t("admins.unlimited")}
                  {...form.register("traffic_limit", { valueAsNumber: true })}
                  value={form.watch("traffic_limit") ?? ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    form.setValue(
                      "traffic_limit",
                      val === "" ? null : parseFloat(val)
                    );
                  }}
                />
              </FormControl>

              <FormControl>
                <FormLabel>{t("admins.telegramId")}</FormLabel>
                <Input
                  type="number"
                  {...form.register("telegram_id", { valueAsNumber: true })}
                  value={form.watch("telegram_id") ?? ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    form.setValue(
                      "telegram_id",
                      val === "" ? null : parseInt(val)
                    );
                  }}
                />
              </FormControl>

              <FormControl>
                <FormLabel>{t("admins.discordWebhook")}</FormLabel>
                <Input {...form.register("discord_webhook")} />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <HStack spacing={3} w="full">
              <Button
                onClick={onClose}
                size="sm"
                variant="outline"
                w="full"
              >
                {t("cancel")}
              </Button>
              <Button
                type="submit"
                size="sm"
                colorScheme="primary"
                w="full"
                leftIcon={loading ? <Spinner size="xs" /> : undefined}
                isLoading={loading}
              >
                {isEditing ? t("apply") : t("admins.createAdmin")}
              </Button>
            </HStack>
          </ModalFooter>
        </form>
      </ModalContent>
    </Modal>
  );
};
