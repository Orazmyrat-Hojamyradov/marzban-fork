import {
  Badge,
  Box,
  Button,
  HStack,
  IconButton,
  Spinner,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  VStack,
  chakra,
  useBreakpointValue,
} from "@chakra-ui/react";
import { ArrowLeftIcon, PencilIcon, TrashIcon, UserPlusIcon } from "@heroicons/react/24/outline";
import { AdminDialog } from "components/AdminDialog";
import { DeleteAdminModal } from "components/DeleteAdminModal";
import { Footer } from "components/Footer";
import { useAdmins } from "contexts/AdminsContext";
import useGetUser from "hooks/useGetUser";
import { FC, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { AdminType } from "types/Admin";

const iconProps = {
  baseStyle: {
    w: 4,
    h: 4,
  },
};

const BackIcon = chakra(ArrowLeftIcon, iconProps);
const EditIcon = chakra(PencilIcon, iconProps);
const DeleteIcon = chakra(TrashIcon, iconProps);
const AddIcon = chakra(UserPlusIcon, iconProps);

const formatTraffic = (bytes: number | null): string => {
  if (bytes === null || bytes === 0) return "-";
  const gb = bytes / (1024 * 1024 * 1024);
  if (gb >= 1) return `${gb.toFixed(1)} GB`;
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(0)} MB`;
};

const formatUserCount = (admin: AdminType, unlimited: string): string => {
  if (admin.user_limit !== null) {
    return `${admin.user_count} / ${admin.user_limit}`;
  }
  return `${admin.user_count} / ${unlimited}`;
};

const formatTrafficUsage = (admin: AdminType, unlimited: string): string => {
  const usage = formatTraffic(admin.users_usage);
  if (admin.traffic_limit !== null) {
    return `${usage} / ${formatTraffic(admin.traffic_limit)}`;
  }
  return `${usage} / ${unlimited}`;
};

const AdminCard: FC<{
  admin: AdminType;
  t: (key: string) => string;
  onEdit: () => void;
  onDelete: () => void;
}> = ({ admin, t, onEdit, onDelete }) => (
  <Box
    border="1px solid"
    borderColor="gray.200"
    _dark={{ borderColor: "gray.600" }}
    borderRadius="lg"
    p={4}
  >
    <HStack justifyContent="space-between" mb={2}>
      <Text fontWeight="semibold" fontSize="md">
        {admin.username}
      </Text>
      <HStack spacing={1}>
        {admin.is_sudo ? (
          <Badge colorScheme="green">Sudo</Badge>
        ) : (
          <Badge colorScheme="gray">Admin</Badge>
        )}
      </HStack>
    </HStack>
    <VStack spacing={1} align="stretch" fontSize="sm" color="gray.600" _dark={{ color: "gray.400" }}>
      <HStack justifyContent="space-between">
        <Text>{t("admins.users")}</Text>
        <Text fontWeight="medium" color="gray.800" _dark={{ color: "gray.200" }}>
          {formatUserCount(admin, t("admins.unlimited"))}
        </Text>
      </HStack>
      <HStack justifyContent="space-between">
        <Text>{t("admins.usersUsage")}</Text>
        <Text fontWeight="medium" color="gray.800" _dark={{ color: "gray.200" }}>
          {formatTrafficUsage(admin, t("admins.unlimited"))}
        </Text>
      </HStack>
    </VStack>
    <HStack justifyContent="flex-end" mt={3} spacing={2}>
      <IconButton
        aria-label="Edit"
        size="sm"
        variant="outline"
        onClick={onEdit}
      >
        <EditIcon />
      </IconButton>
      <IconButton
        aria-label="Delete"
        size="sm"
        variant="outline"
        colorScheme="red"
        onClick={onDelete}
      >
        <DeleteIcon />
      </IconButton>
    </HStack>
  </Box>
);

export const Admins: FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { userData, getUserIsSuccess, getUserIsPending } = useGetUser();
  const {
    admins,
    loading,
    fetchAdmins,
    onCreatingAdmin,
    onEditingAdmin,
    onDeletingAdmin,
  } = useAdmins();
  const useTable = useBreakpointValue({ base: false, md: true });

  useEffect(() => {
    if (!getUserIsPending && getUserIsSuccess && !userData.is_sudo) {
      navigate("/");
    }
  }, [getUserIsPending, getUserIsSuccess, userData]);

  useEffect(() => {
    fetchAdmins();
  }, []);

  if (getUserIsPending) {
    return (
      <VStack justifyContent="center" minH="100vh">
        <Spinner />
      </VStack>
    );
  }

  return (
    <VStack justifyContent="space-between" minH="100vh" p={{ base: 4, md: 6 }} rowGap={4}>
      <Box w="full">
        <HStack justifyContent="space-between" mb={4}>
          <HStack spacing={3}>
            <IconButton
              aria-label="Back"
              size="sm"
              variant="outline"
              onClick={() => navigate("/")}
            >
              <BackIcon />
            </IconButton>
            <Text as="h1" fontWeight="semibold" fontSize={{ base: "xl", md: "2xl" }}>
              {t("admins.title")}
            </Text>
          </HStack>
          <Button
            size="sm"
            colorScheme="primary"
            leftIcon={<AddIcon />}
            onClick={() => onCreatingAdmin(true)}
          >
            {t("admins.createAdmin")}
          </Button>
        </HStack>

        {loading ? (
          <VStack py={10}>
            <Spinner />
          </VStack>
        ) : useTable ? (
          <Box
            overflowX="auto"
            border="1px solid"
            borderColor="gray.200"
            _dark={{ borderColor: "gray.600" }}
            borderRadius="lg"
          >
            <Table variant="simple" size="sm">
              <Thead>
                <Tr>
                  <Th>{t("admins.username")}</Th>
                  <Th>{t("admins.isSudo")}</Th>
                  <Th>{t("admins.users")}</Th>
                  <Th>{t("admins.usersUsage")}</Th>
                  <Th></Th>
                </Tr>
              </Thead>
              <Tbody>
                {admins.map((admin) => (
                  <Tr key={admin.username}>
                    <Td fontWeight="medium">{admin.username}</Td>
                    <Td>
                      {admin.is_sudo ? (
                        <Badge colorScheme="green">Sudo</Badge>
                      ) : (
                        <Badge colorScheme="gray">Admin</Badge>
                      )}
                    </Td>
                    <Td>{formatUserCount(admin, t("admins.unlimited"))}</Td>
                    <Td>{formatTrafficUsage(admin, t("admins.unlimited"))}</Td>
                    <Td>
                      <HStack spacing={1} justifyContent="flex-end">
                        <IconButton
                          aria-label="Edit"
                          size="sm"
                          variant="ghost"
                          onClick={() => onEditingAdmin(admin)}
                        >
                          <EditIcon />
                        </IconButton>
                        <IconButton
                          aria-label="Delete"
                          size="sm"
                          variant="ghost"
                          colorScheme="red"
                          onClick={() => onDeletingAdmin(admin)}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </HStack>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Box>
        ) : (
          <VStack spacing={3} align="stretch">
            {admins.map((admin) => (
              <AdminCard
                key={admin.username}
                admin={admin}
                t={t}
                onEdit={() => onEditingAdmin(admin)}
                onDelete={() => onDeletingAdmin(admin)}
              />
            ))}
          </VStack>
        )}

        <AdminDialog />
        <DeleteAdminModal />
      </Box>
      <Footer />
    </VStack>
  );
};

export default Admins;
