import { fetch } from "service/http";
import { AdminCreate, AdminModify, AdminType } from "types/Admin";
import { create } from "zustand";

type AdminsStateType = {
  admins: AdminType[];
  loading: boolean;
  isCreatingAdmin: boolean;
  editingAdmin: AdminType | null;
  deletingAdmin: AdminType | null;
  onCreatingAdmin: (isCreating: boolean) => void;
  onEditingAdmin: (admin: AdminType | null) => void;
  onDeletingAdmin: (admin: AdminType | null) => void;
  fetchAdmins: () => Promise<void>;
  createAdmin: (body: AdminCreate) => Promise<void>;
  updateAdmin: (username: string, body: AdminModify) => Promise<void>;
  deleteAdmin: (username: string) => Promise<void>;
};

export const useAdmins = create<AdminsStateType>((set, get) => ({
  admins: [],
  loading: true,
  isCreatingAdmin: false,
  editingAdmin: null,
  deletingAdmin: null,
  onCreatingAdmin: (isCreatingAdmin) => set({ isCreatingAdmin }),
  onEditingAdmin: (editingAdmin) => set({ editingAdmin }),
  onDeletingAdmin: (deletingAdmin) => set({ deletingAdmin }),
  fetchAdmins: () => {
    set({ loading: true });
    return fetch("/admins")
      .then((admins: AdminType[]) => {
        set({ admins });
      })
      .finally(() => {
        set({ loading: false });
      });
  },
  createAdmin: (body: AdminCreate) => {
    return fetch("/admin", { method: "POST", body }).then(() => {
      get().fetchAdmins();
    });
  },
  updateAdmin: (username: string, body: AdminModify) => {
    return fetch(`/admin/${username}`, { method: "PUT", body }).then(() => {
      get().fetchAdmins();
    });
  },
  deleteAdmin: (username: string) => {
    return fetch(`/admin/${username}`, { method: "DELETE" }).then(() => {
      get().fetchAdmins();
    });
  },
}));
