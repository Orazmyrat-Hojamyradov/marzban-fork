import {
  Button,
  chakra,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Spinner,
  Text,
  useToast,
} from "@chakra-ui/react";
import { TrashIcon } from "@heroicons/react/24/outline";
import { useAdmins } from "contexts/AdminsContext";
import { FC, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { Icon } from "./Icon";

const DeleteIcon = chakra(TrashIcon, {
  baseStyle: {
    w: 5,
    h: 5,
  },
});

export const DeleteAdminModal: FC = () => {
  const [loading, setLoading] = useState(false);
  const { deletingAdmin, onDeletingAdmin, deleteAdmin } = useAdmins();
  const { t } = useTranslation();
  const toast = useToast();

  const onClose = () => {
    onDeletingAdmin(null);
  };

  const onDelete = () => {
    if (deletingAdmin) {
      if (deletingAdmin.is_sudo) {
        toast({
          title: t("admins.cannotDeleteSudo"),
          status: "warning",
          isClosable: true,
          position: "top",
          duration: 3000,
        });
        return;
      }
      setLoading(true);
      deleteAdmin(deletingAdmin.username)
        .then(() => {
          toast({
            title: t("admins.adminDeleted"),
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
    <Modal isCentered isOpen={!!deletingAdmin} onClose={onClose} size="sm">
      <ModalOverlay bg="blackAlpha.300" backdropFilter="blur(10px)" />
      <ModalContent mx="3">
        <ModalHeader pt={6}>
          <Icon color="red">
            <DeleteIcon />
          </Icon>
        </ModalHeader>
        <ModalCloseButton mt={3} />
        <ModalBody>
          <Text fontWeight="semibold" fontSize="lg">
            {t("admins.deleteAdmin")}
          </Text>
          {deletingAdmin && (
            <Text
              mt={1}
              fontSize="sm"
              _dark={{ color: "gray.400" }}
              color="gray.600"
            >
              <Trans components={{ b: <b /> }}>
                {t("admins.deletePrompt", {
                  username: deletingAdmin.username,
                })}
              </Trans>
            </Text>
          )}
        </ModalBody>
        <ModalFooter display="flex">
          <Button
            size="sm"
            onClick={onClose}
            mr={3}
            w="full"
            variant="outline"
          >
            {t("cancel")}
          </Button>
          <Button
            size="sm"
            w="full"
            colorScheme="red"
            onClick={onDelete}
            isDisabled={deletingAdmin?.is_sudo}
            leftIcon={loading ? <Spinner size="xs" /> : undefined}
          >
            {t("delete")}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};
