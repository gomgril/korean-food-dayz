// The in animation finishes before the first sip; keep its result on the item.
modded class ActionDrink
{
    override protected void OnStartAnimationLoopServer(ActionData action_data)
    {
        super.OnStartAnimationLoopServer(action_data);
        KF_PantryDrink drink=KF_PantryDrink.Cast(action_data.m_MainItem);
        if (drink) drink.KFP_OpenDrink();
    }
    override protected void OnStartAnimationLoopClient(ActionData action_data)
    {
        super.OnStartAnimationLoopClient(action_data);
        KF_PantryDrink drink=KF_PantryDrink.Cast(action_data.m_MainItem);
        if (drink) drink.KFP_OpenDrink();
    }
};
