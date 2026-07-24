# Azure Account Setup

1. Sign up for a [free Azure account](https://azure.microsoft.com/free/) and create an Azure Subscription.
2. Check that you have the necessary permissions:
    * Your Azure account must have `Microsoft.Authorization/roleAssignments/write` permissions, such as [Role Based Access Control Administrator](https://learn.microsoft.com/azure/role-based-access-control/built-in-roles#role-based-access-control-administrator-preview), [User Access Administrator](https://learn.microsoft.com/azure/role-based-access-control/built-in-roles#user-access-administrator), or [Owner](https://learn.microsoft.com/azure/role-based-access-control/built-in-roles#owner).
    * Your Azure account also needs `Microsoft.Resources/deployments/write` permissions on the subscription level.

You can view the permissions for your account and subscription by following the steps below:

- Navigate to the [Azure Portal](https://portal.azure.com/) and click on `Subscriptions` under 'Navigation'.
- Select the subscription you are using for this accelerator from the list.
    - If you try to search for your subscription and it does not come up, make sure no filters are selected.
- Select `Access control (IAM)` and you can see the roles that are assigned to your account for this subscription.
    - If you want to see more information about the roles, you can go to the `Role assignments` tab and search by your account name and then click the role you want to view more information about.

## Required Roles Summary

| **Required Permission/Role** | **Scope** | **Purpose** |
|------------------------------|-----------|-------------|
| **Contributor** | Subscription level | Create and manage Azure resources |
| **User Access Administrator** | Subscription level | Manage user access and role assignments |
| **Role Based Access Control Admin** | Subscription/Resource Group level | Configure RBAC permissions |
| **App Registration Creation** | Microsoft Entra ID | Create and configure authentication (optional) |

## Next Steps

Return to the [Deployment Guide](./DeploymentGuide.md) to continue with your deployment.
