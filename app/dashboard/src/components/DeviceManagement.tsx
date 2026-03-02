import {
  Box,
  Button,
  Flex,
  HStack,
  IconButton,
  Text,
  useColorMode,
  Badge,
  Alert,
  AlertIcon,
  Tooltip,
  VStack,
  SimpleGrid,
  useBreakpointValue,
  Divider,
} from "@chakra-ui/react";
import { ArrowUpTrayIcon } from "@heroicons/react/24/outline";
import { FC } from "react";
import { useTranslation } from "react-i18next";
import { User, UserDevice } from "types/User";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";

dayjs.extend(relativeTime);

interface DeviceManagementProps {
  user: User;
  devices: UserDevice[];
  isLoading: boolean;
  onDeleteDevice: (deviceId: number) => void;
  onDeleteAllDevices: () => void;
}

export const DeviceManagement: FC<DeviceManagementProps> = ({
  user,
  devices,
  isLoading,
  onDeleteDevice,
  onDeleteAllDevices,
}) => {
  const { t } = useTranslation();
  const { colorMode } = useColorMode();
  
  const isMobile = useBreakpointValue({ base: true, md: false });

  const getDeviceName = (device: UserDevice) => {
    if (device.device_model) return device.device_model;
    if (device.platform && device.os_version) {
      return `${device.platform} ${device.os_version}`;
    }
    if (device.platform) return device.platform;
    return "Unknown Device";
  };

  const getDeviceIcon = (device: UserDevice) => {
    const platform = device.platform?.toLowerCase() || "";
    const userAgent = device.user_agent?.toLowerCase() || "";
    
    if (platform.includes("android") || userAgent.includes("android")) {
      return "📱";
    } else if (platform.includes("ios") || userAgent.includes("iphone") || userAgent.includes("ipad")) {
      return "📱";
    } else if (platform.includes("windows")) {
      return "💻";
    } else if (platform.includes("macos") || platform.includes("mac")) {
      return "💻";
    } else if (platform.includes("linux")) {
      return "🖥️";
    }
    return "📡";
  };

  const formatRelativeTime = (dateString: string) => {
    return dayjs(dateString).fromNow();
  };

  const formatFullDate = (dateString: string) => {
    return dayjs(dateString).format("MMM D, YYYY h:mm A");
  };

  const activeDevices = devices.filter(d => !d.disabled);
  const disabledDevicesCount = devices.filter(d => d.disabled).length;

  // Mobile Card View
  if (isMobile) {
    return (
      <Box>
        <Flex justifyContent="space-between" alignItems="center" mb={3}>
          <Text fontSize="md" fontWeight="semibold">
            {t("userDialog.connectedDevices")}
            <Text as="span" fontSize="sm" fontWeight="normal" ml={1}>
              ({activeDevices.length}
              {user.device_limit && user.device_limit > 0 && `/${user.device_limit}`})
            </Text>
          </Text>
          {activeDevices.length > 0 && (
            <Button
              size="xs"
              colorScheme="red"
              variant="outline"
              onClick={onDeleteAllDevices}
              px={2}
            >
              {t("userDialog.deleteAllDevices")}
            </Button>
          )}
        </Flex>

        {disabledDevicesCount > 0 && (
          <Text fontSize="xs" color="gray.500" mb={2}>
            {disabledDevicesCount} blocked
          </Text>
        )}

        {devices.length === 0 ? (
          <Alert status="info" borderRadius="md" fontSize="sm">
            <AlertIcon />
            {t("userDialog.noDevicesConnected")}
          </Alert>
        ) : (
          <VStack spacing={2} align="stretch">
            {devices.map((device) => (
              <Box
                key={device.id}
                p={3}
                borderRadius="lg"
                border="1px solid"
                borderColor={device.disabled ? "gray.300" : "gray.200"}
                bg={device.disabled ? "gray.50" : "white"}
                _dark={{
                  borderColor: device.disabled ? "gray.600" : "gray.700",
                  bg: device.disabled ? "gray.800" : "gray.750",
                }}
                opacity={device.disabled ? 0.6 : 1}
              >
                <Flex justifyContent="space-between" alignItems="flex-start" mb={2}>
                  <HStack spacing={2} align="flex-start">
                    <Text fontSize="2xl" flexShrink={0}>{getDeviceIcon(device)}</Text>
                    <Box minW={0} flex={1}>
                      <Text fontWeight="medium" fontSize="sm" wordBreak="break-word">
                        {getDeviceName(device)}
                      </Text>
                      <HStack spacing={1} mt={1} flexWrap="wrap">
                        {device.platform && (
                          <Badge fontSize="8px" px={1} py={0.5} borderRadius="md" colorScheme={device.disabled ? "gray" : "blue"}>
                            {device.platform}
                          </Badge>
                        )}
                        <Badge fontSize="8px" px={1} py={0.5} borderRadius="md" colorScheme={device.disabled ? "red" : "green"}>
                          {device.disabled ? t("userDialog.blocked") : t("userDialog.active")}
                        </Badge>
                      </HStack>
                    </Box>
                  </HStack>
                </Flex>

                <Divider my={2} />

                <Box fontSize="xs" color="gray.600" _dark={{ color: "gray.400" }}>
                  <Flex justifyContent="space-between" mb={1}>
                    <Text>HWID</Text>
                    <Text fontFamily="mono" fontSize="9px" maxW="120px" isTruncated>
                      {device.hwid}
                    </Text>
                  </Flex>
                  <Flex justifyContent="space-between" mb={1}>
                    <Text>{t("userDialog.lastSeen")}</Text>
                    <Tooltip label={formatFullDate(device.updated_at)}>
                      <Text>{formatRelativeTime(device.updated_at)}</Text>
                    </Tooltip>
                  </Flex>
                </Box>

                {!device.disabled && (
                  <Flex justifyContent="flex-end" mt={2}>
                    <Tooltip label={t("userDialog.blockDevice")}>
                      <IconButton
                        size="sm"
                        colorScheme="orange"
                        variant="outline"
                        aria-label={t("userDialog.blockDevice")}
                        icon={<ArrowUpTrayIcon width="14px" />}
                        onClick={() => onDeleteDevice(device.id)}
                      />
                    </Tooltip>
                  </Flex>
                )}
              </Box>
            ))}
          </VStack>
        )}
      </Box>
    );
  }

  // Tablet/Desktop Table View
  return (
    <Box>
      <Flex justifyContent="space-between" alignItems="center" mb={4}>
        <Text fontSize="lg" fontWeight="semibold">
          {t("userDialog.connectedDevices")} ({activeDevices.length}
          {user.device_limit && user.device_limit > 0 && `/${user.device_limit}`})
          {disabledDevicesCount > 0 && (
            <Text as="span" fontSize="sm" fontWeight="normal" ml={2} color="gray.500">
              ({disabledDevicesCount} blocked)
            </Text>
          )}
        </Text>
        {activeDevices.length > 0 && (
          <Button
            size="sm"
            colorScheme="red"
            variant="outline"
            onClick={onDeleteAllDevices}
          >
            {t("userDialog.deleteAllDevices")}
          </Button>
        )}
      </Flex>

      {devices.length === 0 ? (
        <Alert status="info" borderRadius="md">
          <AlertIcon />
          {t("userDialog.noDevicesConnected")}
        </Alert>
      ) : (
        <Box overflowX="auto">
          <SimpleGrid columns={1} spacing={2}>
            <Box as="table" width="full" fontSize="sm">
              <Box as="thead" bg="gray.50" _dark={{ bg: "gray.800" }}>
                <Box as="tr">
                  <Box as="th" py={3} px={4} textAlign="left" fontWeight="semibold">
                    {t("userDialog.device")}
                  </Box>
                  <Box as="th" py={3} px={4} textAlign="left" fontWeight="semibold">
                    {t("userDialog.platform")}
                  </Box>
                  <Box as="th" py={3} px={4} textAlign="left" fontWeight="semibold">
                    {t("userDialog.hwId")}
                  </Box>
                  <Box as="th" py={3} px={4} textAlign="left" fontWeight="semibold">
                    {t("userDialog.lastSeen")}
                  </Box>
                  <Box as="th" py={3} px={4} textAlign="left" fontWeight="semibold">
                    {t("userDialog.status")}
                  </Box>
                  <Box as="th" py={3} px={4} textAlign="right" fontWeight="semibold">
                    {t("userDialog.actions")}
                  </Box>
                </Box>
              </Box>
              <Box as="tbody">
                {devices.map((device) => (
                  <Box
                    key={device.id}
                    as="tr"
                    opacity={device.disabled ? 0.5 : 1}
                    bg={device.disabled ? "gray.50" : "transparent"}
                    _dark={{ bg: device.disabled ? "gray.800" : "transparent" }}
                    _hover={{ bg: device.disabled ? "gray.100" : "gray.50", _dark: { bg: device.disabled ? "gray.750" : "gray.700" } }}
                  >
                    <Box as="td" py={3} px={4}>
                      <HStack spacing={2} align="flex-start">
                        <Text fontSize="xl" flexShrink={0}>{getDeviceIcon(device)}</Text>
                        <Text fontWeight="medium" wordBreak="break-word" whiteSpace="normal">
                          {getDeviceName(device)}
                        </Text>
                      </HStack>
                    </Box>
                    <Box as="td" py={3} px={4}>
                      {device.platform && (
                        <Badge colorScheme={device.disabled ? "gray" : "blue"} fontSize="xs">
                          {device.platform}
                        </Badge>
                      )}
                    </Box>
                    <Box as="td" py={3} px={4}>
                      <Text fontSize="xs" fontFamily="mono" maxW="150px" isTruncated title={device.hwid}>
                        {device.hwid}
                      </Text>
                    </Box>
                    <Box as="td" py={3} px={4}>
                      <Tooltip label={formatFullDate(device.updated_at)}>
                        <Text>{formatRelativeTime(device.updated_at)}</Text>
                      </Tooltip>
                    </Box>
                    <Box as="td" py={3} px={4}>
                      {device.disabled ? (
                        <Badge colorScheme="red">{t("userDialog.blocked")}</Badge>
                      ) : (
                        <Badge colorScheme="green">{t("userDialog.active")}</Badge>
                      )}
                    </Box>
                    <Box as="td" py={3} px={4}>
                      {!device.disabled && (
                        <Flex justifyContent="flex-end" gap={1}>
                          <Tooltip label={t("userDialog.blockDevice")}>
                            <IconButton
                              size="sm"
                              colorScheme="orange"
                              variant="outline"
                              aria-label={t("userDialog.blockDevice")}
                              icon={<ArrowUpTrayIcon width="14px" />}
                              onClick={() => onDeleteDevice(device.id)}
                            />
                          </Tooltip>
                        </Flex>
                      )}
                    </Box>
                  </Box>
                ))}
              </Box>
            </Box>
          </SimpleGrid>
        </Box>
      )}
    </Box>
  );
};
